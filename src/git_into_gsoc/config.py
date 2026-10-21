"""Runtime configuration for git-into-gsoc."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from git_into_gsoc import __version__

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


class Settings(BaseSettings):
    """Environment-driven settings (prefix `GIG_`)."""

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
    use_gh_cli: bool = True
    github_api_url: str = GITHUB_API
    gsoc_orgs_api_url: str = GSOC_ORGS_API
    gsoc_official_api_url: str = GSOC_OFFICIAL_API
    ecosystems_commits_api_url: str = ECOSYSTEMS_COMMITS_API
    target_year: int = DEFAULT_TARGET_YEAR
    cache_ttl_seconds: int = 3600
    archive_ttl_seconds: int = 86400
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 2
    http_max_retry_wait_seconds: float = 20.0
    max_concurrency: int = 6
    search_min_interval_seconds: float = 2.0
    cache_dir: Path | None = None
    data_dir: Path | None = None
    user_agent: str = f"{_APP_NAME}/{__version__} (+{PROJECT_URL})"

    def resolve_github_token(self) -> str | None:
        return resolve_token(self)[0]

    def github_token_source(self) -> str | None:
        return resolve_token(self)[1]


def resolve_token(settings: Settings) -> tuple[str | None, str | None]:
    """Return (token, source): explicit setting, env vars, then `gh auth token`."""
    if settings.github_token:
        return settings.github_token, "environment"
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value, f"${key}"
    if settings.use_gh_cli:
        token = _gh_cli_token()
        if token:
            return token, "gh auth token"
    return None, None


@lru_cache(maxsize=1)
def _gh_cli_token() -> str | None:
    gh = shutil.which("gh")
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
    return Settings()


def _private_dir(path: Path) -> Path:
    """Create ``path`` readable only by the current user (cached API responses and
    progress notes can include data from private repositories when a token is used)."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        with contextlib.suppress(OSError):
            path.chmod(0o700)
    return path


def cache_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return _private_dir(settings.cache_dir or Path(user_cache_dir(_APP_NAME, _APP_NAME)))


def data_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return _private_dir(settings.data_dir or Path(user_data_dir(_APP_NAME, _APP_NAME)))


def progress_path() -> Path:
    return data_dir() / "progress.json"
