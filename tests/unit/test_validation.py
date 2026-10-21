from __future__ import annotations

import pytest

from git_into_gsoc.errors import InputError
from git_into_gsoc.validation import (
    parse_issue_ref,
    parse_repo,
    search_term,
    split_csv,
    validate_login,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sympy/sympy", ("sympy", "sympy")),
        ("https://github.com/sympy/sympy", ("sympy", "sympy")),
        ("github.com/numpy/numpy.git", ("numpy", "numpy")),
        ("https://github.com/rust-lang/rust/issues/1", ("rust-lang", "rust")),
        (" pandas-dev/pandas/ ", ("pandas-dev", "pandas")),
    ],
)
def test_parse_repo_accepts_names_and_urls(raw: str, expected: tuple[str, str]) -> None:
    assert parse_repo(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["sympy", "../etc/passwd", "owner/..", "https://gitlab.com/a/b", "a b/c", "-bad/repo", ""],
)
def test_parse_repo_rejects_invalid(raw: str) -> None:
    with pytest.raises(InputError):
        parse_repo(raw)


def test_parse_issue_ref_forms() -> None:
    assert parse_issue_ref("sympy/sympy#123") == ("sympy", "sympy", 123)
    assert parse_issue_ref("https://github.com/a/b/issues/7") == ("a", "b", 7)
    assert parse_issue_ref("https://github.com/a/b/pull/9") == ("a", "b", 9)
    assert parse_issue_ref("a/b", 5) == ("a", "b", 5)
    with pytest.raises(InputError):
        parse_issue_ref("a/b")
    with pytest.raises(InputError):
        parse_issue_ref("a/b#zero")


def test_validate_login() -> None:
    assert validate_login("@octocat") == "octocat"
    with pytest.raises(InputError):
        validate_login("not a user")
    with pytest.raises(InputError):
        validate_login("x" * 40)


def test_search_term_strips_qualifier_injection() -> None:
    assert search_term("python") == "python"
    assert search_term("good first issue") == '"good first issue"'
    assert search_term('c++" is:pr') == '"c++ is pr"'
    with pytest.raises(InputError):
        search_term('"":')


def test_split_csv() -> None:
    assert split_csv("python, rust,,") == ["python", "rust"]
    assert split_csv(["a", " ", "b "]) == ["a", "b"]
    assert split_csv(None) == []


def test_issue_refs_from_pasted_links_and_remotes() -> None:
    assert parse_issue_ref("https://github.com/sympy/sympy/issues/28050#issuecomment-1") == (
        "sympy",
        "sympy",
        28050,
    )
    assert parse_issue_ref("https://github.com/sympy/sympy/issues/7?foo=bar#x") == (
        "sympy",
        "sympy",
        7,
    )
    assert parse_issue_ref("github.com/sympy/sympy/pull/9#discussion_r1") == ("sympy", "sympy", 9)
    assert parse_issue_ref("sympy/sympy#12") == ("sympy", "sympy", 12)
    assert parse_repo("git@github.com:sympy/sympy.git") == ("sympy", "sympy")
    assert parse_repo("ssh://git@github.com/sympy/sympy.git") == ("sympy", "sympy")
