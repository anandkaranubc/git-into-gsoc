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
