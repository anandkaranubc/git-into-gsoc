"""Errors a beginner hits by mistyping a name say what is wrong, not just an HTTP code."""

from __future__ import annotations

import httpx
import pytest
import respx

from git_into_gsoc.errors import NotFoundError, RateLimitError
from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.http_client import HttpError

API = "https://api.github.com"


@respx.mock
def test_a_missing_repository_issue_or_user_is_named() -> None:
    respx.get(url__startswith=API).mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    gh = GitHubClient()
    with pytest.raises(NotFoundError) as repo:
        gh.get_repo("sympy", "sympyy")
    assert str(repo.value) == "GitHub has no public repository sympy/sympyy"
    assert repo.value.hint and "https://github.com/sympy/sympyy" in repo.value.hint
    with pytest.raises(NotFoundError) as issue:
        gh.get_issue("sympy", "sympy", 99999999)
    assert str(issue.value) == "sympy/sympy has no issue or pull request #99999999"
    with pytest.raises(NotFoundError) as user:
        gh.get_user("no-such-user-zz9")
    assert str(user.value) == "No GitHub user or organization is named no-such-user-zz9"


@respx.mock
def test_a_search_naming_a_missing_user_explains_the_422() -> None:
    body = {
        "message": "Validation Failed",
        "errors": [
            {
                "message": "The listed users and repositories cannot be searched either because "
                "the resources do not exist or you do not have permission to view them.",
                "resource": "Search",
                "field": "q",
                "code": "invalid",
            }
        ],
    }
    respx.get(f"{API}/search/issues").mock(return_value=httpx.Response(422, json=body))
    with pytest.raises(HttpError) as caught:
        GitHubClient().search_issues("author:no-such-user-zz9 is:pr")
    assert "cannot be searched" in str(caught.value)
    assert caught.value.hint and "spelling" in caught.value.hint


def test_secondary_search_limit_does_not_suggest_a_token_to_someone_who_has_one() -> None:
    with_token = RateLimitError("limit", authenticated=True, resource="search")
    assert with_token.hint and "gh auth login" not in with_token.hint
    without = RateLimitError("limit", authenticated=False, resource="search")
    assert without.hint and "gh auth login" in without.hint


def test_a_gitlab_link_says_what_to_do_instead() -> None:
    from git_into_gsoc.errors import InputError
    from git_into_gsoc.validation import parse_repo

    with pytest.raises(InputError) as caught:
        parse_repo("https://gitlab.com/inkscape/inkscape")
    assert caught.value.hint and "GitHub only" in caught.value.hint


def _refused() -> str:
    from git_into_gsoc import config

    config.get_settings.cache_clear()
    with respx.mock:
        respx.get(url__startswith=API).mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        with pytest.raises(HttpError) as refused:
            GitHubClient().get_repo("sympy", "sympy")
    assert refused.value.status_code == 401
    return refused.value.hint or ""


def test_a_refused_token_hint_names_where_the_token_came_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A live check of 0.24.0 with a revoked GITHUB_TOKEN said "Run `gh auth login`",
    # which cannot help while that variable is set: it is read first.
    from git_into_gsoc import config

    monkeypatch.setenv("GITHUB_TOKEN", "revoked-token")
    hint = _refused()
    assert hint.startswith("GitHub refused the token in GITHUB_TOKEN")
    assert "remove the variable from your environment and your shell profile" in hint
    monkeypatch.delenv("GITHUB_TOKEN")

    monkeypatch.setattr(config, "_gh_cli_token", lambda: "expired-gh-token")
    monkeypatch.setenv("GIG_USE_GH_CLI", "true")
    assert _refused() == (
        "GitHub refused the token from `gh auth login`; it may have expired or been "
        "revoked. Run `gh auth login` again."
    )
    monkeypatch.setenv("GIG_USE_GH_CLI", "false")

    with open(".env", "w", encoding="utf-8") as env:  # the test runs in tmp_path
        env.write("GITHUB_TOKEN=from-dotenv\n")
    assert config.resolve_token(config.Settings()) == ("from-dotenv", ".env file")
    assert "the .env file in this folder" in _refused()


def test_a_refusal_from_another_host_does_not_blame_the_github_token() -> None:
    from git_into_gsoc.http_client import _refused_token_hint

    hint = _refused_token_hint("https://gitlab.gnome.org/api/v4/projects/1", None)
    assert hint == (
        "gitlab.gnome.org asked for a sign-in this tool does not have. Open the page in a browser."
    )
    assert "GitHub" not in _refused_token_hint("https://notgithub.com/x", None)


def test_doctor_prints_the_hint_when_the_github_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    from git_into_gsoc import cli
    from git_into_gsoc.cli import app

    class Refusing:
        def rate_limit(self) -> dict[str, int]:
            raise HttpError("HTTP 401 from api.github.com", status_code=401, hint="Replace it.")

    monkeypatch.setattr(cli, "_toolkit", lambda: Refusing())
    monkeypatch.setattr(cli, "_reachable", lambda *a, **k: "ok")
    result = CliRunner().invoke(app, ["doctor"])
    assert "GitHub check failed" in result.output and "  Replace it." in result.output
