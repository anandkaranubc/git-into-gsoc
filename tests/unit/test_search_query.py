from __future__ import annotations

from git_into_gsoc.github.search import MAX_QUERY_CHARS, build_issue_query, or_group


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
    assert query.count(" OR ") < 60


def test_build_issue_query_without_groups() -> None:
    assert build_issue_query(base=["is:issue"], labels=[], orgs=[]) == "is:issue"
    assert (
        build_issue_query(base=["is:issue"], labels=["bug"], orgs=["acme"])
        == "is:issue label:bug org:acme"
    )
