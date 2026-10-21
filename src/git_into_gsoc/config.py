"""Runtime configuration for git-into-gsoc."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TARGET_YEAR = 2027
LATEST_ARCHIVED_YEAR = 2026
GSOC_ORGS_API = "https://api.gsocorganizations.dev"
GITHUB_API = "https://api.github.com"
OFFICIAL_GSOC_HOME = "https://summerofcode.withgoogle.com"
OFFICIAL_RESOURCES = "https://developers.google.com/open-source/gsoc/resources"
OFFICIAL_AI_GUIDANCE = "https://developers.google.com/open-source/gsoc/resources/ai_guidance"
OFFICIAL_CONTRIBUTOR_GUIDE = "https://google.github.io/gsocguides/student/"
OFFICIAL_SPAM_GUIDANCE = "https://developers.google.com/open-source/gsoc/resources/spam_proposals"


class Settings(BaseSettings):
    """Environment-driven settings."""

    model_config = SettingsConfigDict(
        env_prefix="GIG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")
    github_api_url: str = GITHUB_API
    gsoc_orgs_api_url: str = GSOC_ORGS_API
    target_year: int = DEFAULT_TARGET_YEAR
    cache_ttl_seconds: int = 3600
    http_timeout_seconds: float = 30.0
    user_agent: str = "git-into-gsoc/0.1.0 (+https://github.com/anandkaranubc/git-into-gsoc)"

    def resolve_github_token(self) -> str | None:
        """Prefer explicit setting, then common env vars used by gh CLI."""
        if self.github_token:
            return self.github_token
        for key in ("GITHUB_TOKEN", "GH_TOKEN"):
            value = os.environ.get(key)
            if value:
                return value
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def cache_dir() -> Path:
    path = Path(user_cache_dir("git-into-gsoc", "git-into-gsoc"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = Path(user_data_dir("git-into-gsoc", "git-into-gsoc"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def progress_path() -> Path:
    return data_dir() / "progress.json"
