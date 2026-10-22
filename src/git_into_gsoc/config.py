"""Runtime configuration for git-into-gsoc."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir, user_data_dir
from pydantic import AliasChoices, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from git_into_gsoc import __version__
from git_into_gsoc.programs import find_program

DEFAULT_TARGET_YEAR = 2027
LATEST_ARCHIVED_YEAR = 2026
GSOC_ORGS_API = "https://api.gsocorganizations.dev"
GSOC_OFFICIAL_API = "https://summerofcode.withgoogle.com/api"
GITHUB_API = "https://api.github.com"
ECOSYSTEMS_COMMITS_API = "https://commits.ecosyste.ms/api/v1"
OFFICIAL_GSOC_HOME = "https://summerofcode.withgoogle.com"
OFFICIAL_RESOURCES = "https://developers.google.com/open-source/gsoc/resources"
OFFICIAL_TIMELINE = "https://developers.google.com/open-source/gsoc/timeline"
OFFICIAL_AI_GUIDANCE = "https://developers.google.com/open-source/gsoc/resources/ai_guidance"
OFFICIAL_CONTRIBUTOR_GUIDE = "https://google.github.io/gsocguides/student/"
OFFICIAL_SPAM_GUIDANCE = "https://developers.google.com/open-source/gsoc/resources/spam_proposals"
PROJECT_URL = "https://github.com/anandkaranubc/git-into-gsoc"

_APP_NAME = "git-into-gsoc"


# A `.env` in the current folder may belong to a repository someone just cloned, and
# assistants start the MCP server inside the project folder. Such a file may set the
# token and ordinary settings, but never where requests go (the token is sent there)
# or where progress is read and written (a planted progress.json would put someone
# else's words in the contributor's notes). These come from the real environment only.
ENV_ONLY_FIELDS = frozenset(
    {
        "github_api_url",
        "gsoc_orgs_api_url",
        "gsoc_official_api_url",
        "ecosystems_commits_api_url",
        "cache_dir",
        "data_dir",
        # The GitLab token is sent to this host, so a cloned repository's .env must not
        # be able to point it at another server.
        "gitlab_host",
        "gig_gitlab_host",
    }
)
log = logging.getLogger(__name__)


class _DotEnvWithoutRedirects(PydanticBaseSettingsSource):
    """The `.env` source minus ENV_ONLY_FIELDS."""

    def __init__(self, settings_cls: type[BaseSettings], inner: PydanticBaseSettingsSource):
        super().__init__(settings_cls)
        self._inner = inner

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        values = self._inner()
        ignored = sorted(key for key in values if key.lower() in ENV_ONLY_FIELDS)
        if ignored:
            log.warning(
                "Ignored %s from .env in %s: set these in the environment instead.",
                ", ".join(
                    key.upper() if key.lower().startswith("gig_") else f"GIG_{key.upper()}"
                    for key in ignored
                ),
                Path.cwd(),
            )
        return {k: v for k, v in values.items() if k.lower() not in ENV_ONLY_FIELDS}


class Settings(BaseSettings):
    """Settings from the environment (prefix `GIG_`) and a `.env` file in the current
    folder.

    The fields in ENV_ONLY_FIELDS are never read from `.env`. The GitHub token also
    comes from GITHUB_TOKEN, GH_TOKEN, or `gh auth token`; see `resolve_token`.
    """

    model_config = SettingsConfigDict(
        env_prefix="GIG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GIG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"),
        repr=False,
    )
    # A GitLab token reads issue comments, which GitLab hides without a sign-in. It is
    # sent only to `gitlab_host` (tokens belong to one GitLab server).
    gitlab_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GIG_GITLAB_TOKEN", "GITLAB_TOKEN"),
        repr=False,
    )
    gitlab_host: str = Field(
        default="gitlab.com", validation_alias=AliasChoices("GIG_GITLAB_HOST", "GITLAB_HOST")
    )
    use_gh_cli: bool = True
    github_api_url: str = GITHUB_API
    gsoc_orgs_api_url: str = GSOC_ORGS_API
    gsoc_official_api_url: str = GSOC_OFFICIAL_API
    ecosystems_commits_api_url: str = ECOSYSTEMS_COMMITS_API
    target_year: int = DEFAULT_TARGET_YEAR
    cache_ttl_seconds: int = 3600
    # Entries untouched this long are deleted, then the oldest until under the size cap.
    # Zero or less turns a limit off.
    cache_max_age_days: int = 30
    cache_max_mb: int = 500
    archive_ttl_seconds: int = 86400
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 2
    http_max_retry_wait_seconds: float = 20.0
    max_concurrency: int = 6
    search_min_interval_seconds: float = 2.0
    cache_dir: Path | None = None
    data_dir: Path | None = None
    user_agent: str = f"{_APP_NAME}/{__version__} (+{PROJECT_URL})"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            _DotEnvWithoutRedirects(settings_cls, dotenv_settings),
            file_secret_settings,
        )

    def resolve_github_token(self) -> str | None:
        return resolve_token(self)[0]

    def github_token_source(self) -> str | None:
        return resolve_token(self)[1]


# A value such as "$GITHUB_TOKEN" or "${user_config.github_token}" means a host copied a
# config entry without filling it in (Antigravity does this with extension env values).
# Sent to GitHub it would fail every request, so it counts as no token at all.
_PLACEHOLDER = re.compile(r"^\$\{?[A-Za-z_][A-Za-z0-9_.]*\}?$")


def _usable(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value and not _PLACEHOLDER.match(value) else None


def resolve_token(settings: Settings) -> tuple[str | None, str | None]:
    """Return (token, source): explicit setting, env vars, then `gh auth token`."""
    if token := _usable(settings.github_token):
        return token, "environment"
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if value := _usable(os.environ.get(key)):
            return value, f"${key}"
    if settings.use_gh_cli:
        token = _gh_cli_token()
        if token:
            return token, "gh auth token"
    return None, None


@lru_cache(maxsize=1)
def _gh_cli_token() -> str | None:
    gh = find_program("gh")
    if not gh:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The settings, read once per process. Tests call `get_settings.cache_clear()`
    after changing the environment."""
    return Settings()


def _private_dir(path: Path) -> Path:
    """Create ``path`` readable only by the current user (cached API responses and
    progress notes can include data from private repositories when a token is used)."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        with contextlib.suppress(OSError):
            path.chmod(0o700)
    return path


def cache_location(settings: Settings | None = None) -> Path:
    """Where the cache lives, without creating it."""
    settings = settings or get_settings()
    return settings.cache_dir or Path(user_cache_dir(_APP_NAME, _APP_NAME))


def data_location(settings: Settings | None = None) -> Path:
    """Where the progress file lives, without creating it."""
    settings = settings or get_settings()
    return settings.data_dir or Path(user_data_dir(_APP_NAME, _APP_NAME))


def cache_dir(settings: Settings | None = None) -> Path:
    return _private_dir(cache_location(settings))


def data_dir(settings: Settings | None = None) -> Path:
    return _private_dir(data_location(settings))


def progress_path() -> Path:
    return data_dir() / "progress.json"


def latest_program_year(settings: Settings | None = None) -> int:
    """The newest year worth asking about: the target year, or next calendar year."""
    from datetime import UTC, datetime

    target = (settings or get_settings()).target_year
    return max(target, datetime.now(UTC).year + 1)
