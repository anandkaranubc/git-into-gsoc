"""Settings: where the GitHub token comes from, placeholders, and what a `.env` in the current
folder may and may not set."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_into_gsoc import config
from git_into_gsoc.config import Settings, resolve_token


def test_explicit_env_token_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    token, source = resolve_token(Settings())
    assert token == "from-env"
    assert source == "environment"


def test_gh_token_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "gh-env")
    assert Settings().resolve_github_token() == "gh-env"


def test_falls_back_to_gh_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_gh_cli_token", lambda: "from-gh")
    settings = Settings(use_gh_cli=True)
    assert settings.resolve_github_token() == "from-gh"
    assert settings.github_token_source() == "gh auth token"


def test_gh_cli_fallback_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_gh_cli_token", lambda: "from-gh")
    assert Settings(use_gh_cli=False).resolve_github_token() is None


@pytest.mark.parametrize(
    "placeholder", ["$GITHUB_TOKEN", "${GH_TOKEN}", "${user_config.github_token}"]
)
def test_a_placeholder_a_host_did_not_fill_in_is_no_token(
    monkeypatch: pytest.MonkeyPatch, placeholder: str
) -> None:
    # Antigravity copies an extension's env values literally, so the server can see
    # GITHUB_TOKEN="$GITHUB_TOKEN"; that must fall through to `gh auth token`.
    for key in ("GIG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.setenv(key, placeholder)
    monkeypatch.setattr(config, "_gh_cli_token", lambda: "from-gh")
    assert resolve_token(Settings(use_gh_cli=True)) == ("from-gh", "gh auth token")


def test_an_empty_token_variable_is_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # Gemini CLI fills a named but unset variable with "".
    for key in ("GIG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.setenv(key, "")
    assert resolve_token(Settings(use_gh_cli=False)) == (None, None)


def test_token_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret")
    assert "super-secret" not in repr(Settings())


def test_dirs_follow_settings(tmp_path: object) -> None:
    settings = config.get_settings()
    assert "cache" in str(config.cache_dir(settings))
    assert "data" in str(config.data_dir(settings))


def test_a_dotenv_in_the_current_folder_cannot_redirect_requests_or_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A cloned repository's .env must not send the token elsewhere or plant progress."""
    import logging

    from git_into_gsoc.config import ENV_ONLY_FIELDS, Settings

    monkeypatch.delenv("GIG_DATA_DIR")
    monkeypatch.delenv("GIG_CACHE_DIR")
    (tmp_path / ".env").write_text(
        "GIG_GITHUB_API_URL=https://attacker.example/api\n"
        "GIG_GSOC_OFFICIAL_API_URL=https://attacker.example/gsoc\n"
        "GIG_DATA_DIR=.\n"
        "GIG_CACHE_DIR=.\n"
        "GITHUB_TOKEN=from-dotenv\n"
        "GIG_CACHE_TTL_SECONDS=5\n",
        encoding="utf-8",
    )
    with caplog.at_level(logging.WARNING, logger="git_into_gsoc.config"):
        settings = Settings()
    assert settings.github_api_url == "https://api.github.com"
    assert "attacker" not in settings.gsoc_official_api_url
    assert settings.data_dir is None and settings.cache_dir is None
    # Ordinary settings and the documented token still come from .env.
    assert settings.github_token == "from-dotenv" and settings.cache_ttl_seconds == 5
    assert "GIG_GITHUB_API_URL" in caplog.text and "GIG_DATA_DIR" in caplog.text
    assert {"github_api_url", "data_dir", "cache_dir"} <= ENV_ONLY_FIELDS


def test_the_environment_can_still_point_at_another_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from git_into_gsoc.config import Settings

    monkeypatch.setenv("GIG_GITHUB_API_URL", "https://github.example.com/api/v3")
    assert Settings().github_api_url == "https://github.example.com/api/v3"


@pytest.mark.parametrize("name", ["GITLAB_HOST", "GIG_GITLAB_HOST"])
def test_a_dotenv_cannot_send_the_gitlab_token_to_another_host(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from git_into_gsoc.config import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-real")
    (tmp_path / ".env").write_text(f"{name}=attacker.example\n", encoding="utf-8")
    settings = Settings()
    assert settings.gitlab_host == "gitlab.com"
    monkeypatch.setenv("GITLAB_HOST", "gitlab.gnome.org")
    assert Settings().gitlab_host == "gitlab.gnome.org"  # the real environment still works
