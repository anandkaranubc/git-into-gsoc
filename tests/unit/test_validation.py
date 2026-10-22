"""Input validation: repository names, issue references, logins, search terms, years, and
skill words."""

from __future__ import annotations

import pytest

from git_into_gsoc.errors import InputError
from git_into_gsoc.validation import (
    parse_issue_ref,
    parse_repo,
    search_term,
    split_csv,
    validate_login,
    validate_year,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sympy/sympy", ("sympy", "sympy")),
        ("https://github.com/sympy/sympy", ("sympy", "sympy")),
        ("github.com/numpy/numpy.git", ("numpy", "numpy")),
        ("https://github.com/rust-lang/rust/issues/1", ("rust-lang", "rust")),
        (" pandas-dev/pandas/ ", ("pandas-dev", "pandas")),
        ("https://github.com/sympy/sympy/tree/master/doc", ("sympy", "sympy")),
    ],
)
def test_parse_repo_accepts_names_and_urls(raw: str, expected: tuple[str, str]) -> None:
    assert parse_repo(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "sympy",
        "../etc/passwd",
        "owner/..",
        "https://gitlab.com/a/b",
        "a b/c",
        "-bad/repo",
        "",
        "a/b/c",  # used to reach the API and come back as "HTTP 404 from api.github.com"
    ],
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


def test_an_issue_on_another_site_gets_advice_that_is_true() -> None:
    # The old hint said "This tool reads GitHub only. For a project on GitLab...",
    # although `issue` reads GitLab links. BRL-CAD and GNU projects work elsewhere.
    with pytest.raises(InputError) as info:
        parse_issue_ref("https://sourceforge.net/p/brlcad/bugs/1/")
    assert str(info.value).startswith("Not a GitHub issue link")
    assert "also reads issue links from any GitLab server" in (info.value.hint or "")
    assert "read the whole thread for claims" in (info.value.hint or "")
    with pytest.raises(InputError) as repo_info:
        parse_repo("https://codeberg.org/a/b")
    assert (repo_info.value.hint or "").startswith("This command reads GitHub only")


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


@pytest.mark.parametrize("year", [1999, 2004, 3000, -1])
def test_years_outside_the_program_are_rejected(year: int) -> None:
    with pytest.raises(InputError) as caught:
        validate_year(year, latest=2027)
    assert "2005" in str(caught.value)


def test_years_inside_the_program_pass() -> None:
    assert validate_year(None, latest=2027) is None
    assert validate_year(0, latest=2027) is None  # MCP tools send 0 for "not given"
    assert validate_year(2005, latest=2027) == 2005
    assert validate_year(2027, latest=2027) == 2027


def test_program_and_org_list_refuse_years_gsoc_never_had() -> None:
    from git_into_gsoc.gsoc.client import GSoCClient
    from git_into_gsoc.service import GSoCToolkit

    # `orgs --year 1999` showed the 2026 list saying "live sources unreachable";
    # `program --year 3000` projected 2026 dates 974 years forward.
    with pytest.raises(InputError):
        GSoCClient().catalog(1999)
    with pytest.raises(InputError):
        GSoCToolkit().program_info(3000)
    with pytest.raises(InputError):
        GSoCToolkit().program_info(2004)


def test_plain_skill_drops_level_words() -> None:
    from git_into_gsoc.validation import plain_skill

    # A simulated beginner saved "a little python"; orgs then matched nothing.
    assert plain_skill("a little python") == "python"
    assert plain_skill("basic C++") == "C++"
    assert plain_skill("Rust (learning)") == "Rust"
    assert plain_skill("machine learning") == "machine learning"
    assert plain_skill("advanced") == "advanced"


def test_a_project_on_another_site_is_named_as_such_without_its_scheme() -> None:
    # "gitlab.com/inkscape/inkscape" was "Repository must look like owner/repo", with
    # GitHub examples; a GitHub owner never has a dot, so this is another site.
    for raw in ("gitlab.com/inkscape/inkscape", "salsa.debian.org/a/b"):
        with pytest.raises(InputError, match=r"Not a github\.com URL") as found:
            parse_repo(raw)
        assert "`git-into-gsoc issue` does read" in (found.value.hint or "")
    assert parse_repo("github.com/sympy/sympy") == ("sympy", "sympy")
    assert parse_repo("sympy/sympy.github.io") == ("sympy", "sympy.github.io")
