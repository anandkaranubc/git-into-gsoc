"""GitHub search queries: OR groups, owner limits, label values, and language families."""

from __future__ import annotations

from git_into_gsoc.github.search import (
    MAX_OWNER_FILTERS,
    MAX_QUERY_CHARS,
    build_issue_query,
    language_group,
    or_group,
)


def test_or_group_quotes_and_groups() -> None:
    assert or_group("org", ["zulip"]) == "org:zulip"
    assert or_group("org", ["zulip", "oppia"]) == "(org:zulip OR org:oppia)"
    assert (
        or_group("label", ["good first issue", "E-easy"])
        == '(label:"good first issue" OR label:E-easy)'
    )
    assert or_group("org", []) == ""


def test_build_issue_query_groups_and_respects_length() -> None:
    query = build_issue_query(
        base=["is:issue", "is:open", "no:assignee", "-linked:pr", "archived:false"],
        labels=["good first issue", "help wanted"],
        orgs=[f"org{i}" for i in range(60)],
    )
    assert query.startswith("is:issue is:open no:assignee -linked:pr archived:false")
    assert '(label:"good first issue" OR label:"help wanted")' in query
    assert "(org:org0 OR org:org1" in query
    assert len(query) <= MAX_QUERY_CHARS
    assert query.count("org:") == MAX_OWNER_FILTERS  # GitHub rejects 16 or more


def test_build_issue_query_keeps_every_org_github_accepts() -> None:
    # The old 256-character budget silently dropped three of eight recommended orgs.
    owners = ["chicagopcdc", "openmrs", "cBioPortal", "jitsi", "accordproject"]
    owners += ["laurent22", "I-TECH-UW", "owasp"]
    base = ["is:issue", "is:open", "no:assignee", "-linked:pr", "archived:false"]
    base += ["(language:javascript OR language:typescript)", "updated:>=2025-10-21"]
    query = build_issue_query(
        base=base,
        labels=["good first issue", "help wanted"],
        orgs=owners,
    )
    assert all(f"org:{o}" in query for o in owners)


def test_repo_filters_count_toward_the_owner_limit() -> None:
    repos = or_group("repo", [f"a/r{i}" for i in range(5)])
    query = build_issue_query(
        base=["is:issue"], labels=[], orgs=[f"o{i}" for i in range(20)], extra=[repos]
    )
    assert query.count("repo:") + query.count("org:") == MAX_OWNER_FILTERS


def test_build_issue_query_without_groups() -> None:
    assert build_issue_query(base=["is:issue"], labels=[], orgs=[]) == "is:issue"
    assert (
        build_issue_query(base=["is:issue"], labels=["bug"], orgs=["acme"])
        == "is:issue label:bug org:acme"
    )


def test_label_values_keep_colons_and_emoji() -> None:
    assert or_group("label", ["Difficulty: Easy"]) == 'label:"Difficulty: Easy"'
    assert or_group("label", ["🌱 Good first issue"]) == 'label:"🌱 Good first issue"'
    assert or_group("label", ["E-easy"]) == "label:E-easy"
    assert or_group("label", ['bad"quote']) == "label:badquote"


def test_html_and_css_also_search_the_languages_web_projects_are_tagged_with() -> None:
    # GitHub names a repository after its main language; GSoC orgs that list HTML
    # had no repositories tagged HTML with free beginner issues.
    assert language_group("HTML") == (
        "(language:html OR language:css OR language:vue OR language:javascript "
        "OR language:typescript)"
    )
    assert "language:scss" in language_group("css")
    assert language_group("python") == "language:python"
