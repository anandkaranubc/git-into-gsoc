"""Organizations that say they sit out the coming GSoC move down, with the post as the reason."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.errors import HttpError
from git_into_gsoc.service import GSoCToolkit


def _post(status: str, url: str, *, by_maintainer: bool = True, source: str = "") -> dict[str, Any]:
    post = {"status": status, "url": url, "title": "GSoC 2027", "by_maintainer": by_maintainer}
    return post | ({"source": source} if source else {})


ORGS = [
    {"name": "Learning Unlimited", "github_orgs": ["learning-unlimited"], "caveats": ["old"]},
    {"name": "Oppia Foundation", "github_orgs": ["oppia"]},
    {"name": "OSM", "github_orgs": ["osm-search"]},
    {"name": "Applicants only", "github_orgs": ["someone"]},
    {"name": "Umbrella", "github_orgs": []},
]
POSTS = {
    "learning-unlimited": [_post("not_taking_part", "https://wiki/home", source="wiki")],
    "oppia": [_post("mentions", "https://github.com/oppia/oppia/issues/27409")],
    "osm-search": [_post("undecided", "https://github.com/osm-search/Nominatim/issues/4225")],
    # An applicant's "I will not take part in anything else" is not the organization speaking.
    "someone": [_post("not_taking_part", "https://x/1", by_maintainer=False)],
}


def test_sitting_out_moves_last_and_posts_become_evidence(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(
        toolkit.github, "gsoc_year_posts", lambda owners, year: POSTS.get(owners[0], [])
    )
    checked = toolkit.check_participation(ORGS, year=2027)
    assert [o["name"] for o in checked] == [
        "Oppia Foundation",
        "OSM",
        "Applicants only",
        "Umbrella",
        "Learning Unlimited",
    ]
    by_name = {o["name"]: o for o in checked}
    sitting_out = by_name["Learning Unlimited"]
    assert sitting_out["participation"]["status"] == "not_taking_part"
    assert sitting_out["caveats"] == [
        "Says it will not take part in GSoC 2027: https://wiki/home",
        "old",
    ]
    assert by_name["Oppia Foundation"]["participation"]["status"] == "posted"
    assert by_name["Oppia Foundation"]["readiness"][0].startswith("Its maintainers posted")
    assert by_name["OSM"]["caveats"][-1].startswith("Has not decided about GSoC 2027")
    assert by_name["Applicants only"]["participation"] == {"status": "no_post"}
    assert "participation" not in by_name["Umbrella"]
    assert "participation" not in ORGS[0]  # the input is left alone


def test_a_failed_check_is_unknown_and_never_raises(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()

    def down(owners: list[str], year: int) -> list[dict[str, Any]]:
        raise HttpError("GitHub search is rate limited")

    monkeypatch.setattr(toolkit.github, "gsoc_year_posts", down)
    monkeypatch.setattr(toolkit.github, "wiki_year_posts", lambda owners, year: [])
    checked = toolkit.check_participation(ORGS[:2], year=2027, check=1)
    assert checked[0]["participation"] == {"status": "unknown"}
    assert "participation" not in checked[1]  # only the first `check` are looked at


def test_this_year_in_a_post_means_the_coming_program_only_out_of_season() -> None:
    from git_into_gsoc.github.announcements import upcoming_year

    assert upcoming_year("2026-10-04") == 2027  # after a program ends
    assert upcoming_year("2027-01-20") == 2027  # before organizations apply
    assert upcoming_year("2026-05-10") is None  # a program is under way
    assert upcoming_year("") is None


def _issue(body: str, created: str, role: str = "CONTRIBUTOR") -> dict[str, Any]:
    return {
        "body": body,
        "created_at": f"{created}T10:00:00Z",
        "author_association": role,
        "html_url": "https://github.com/lab/lab/issues/7",
        "repository_url": "https://api.github.com/repos/lab/lab",
        "number": 7,
        "user": {"login": "reporter"},
    }


def test_a_statement_in_a_body_without_a_year_is_a_dated_report() -> None:
    from git_into_gsoc.github.announcements import reported_statements

    sympy = _issue(
        "Please test the new assumptions. It's likely that as a result of this we will not "
        "participate in GSoC this year.",
        "2026-10-04",
    )
    found = reported_statements([sympy], year=2027)
    assert len(found) == 1 and found[0]["status"] == "reported"
    assert "will not participate in GSoC this year" in found[0]["title"]
    assert found[0]["by_maintainer"] is False and found[0]["created_at"] == "2026-10-04"
    # Another year named, mid-season with no year, or no statement at all: nothing.
    past = _issue("We will not participate in GSoC 2026.", "2026-10-04", "MEMBER")
    mid = _issue("We will not participate in GSoC this year.", "2026-05-10", "MEMBER")
    plain = _issue("This is a GSoC idea about parsers.", "2026-10-04", "MEMBER")
    assert reported_statements([past, mid, plain], year=2027) == []


def test_a_report_is_used_only_when_nothing_better_was_posted() -> None:
    from git_into_gsoc.service import participation_from

    report = _post("reported", "https://x/report", by_maintainer=False) | {
        "created_at": "2026-10-04"
    }
    alone = participation_from({"posts": [report]})
    assert alone["status"] == "reported" and alone["date"] == "2026-10-04"
    assert alone["by_maintainer"] is False
    official = _post("mentions", "https://x/official")
    assert participation_from({"posts": [report, official]})["status"] == "posted"


def test_a_live_check_finding_nothing_keeps_the_monthly_statement(monkeypatch: Any) -> None:
    toolkit = GSoCToolkit()
    monkeypatch.setattr(toolkit.github, "gsoc_year_posts", lambda owners, year: [])
    said = {"status": "reported", "url": "https://x/report", "quote": "no GSoC this year"}
    orgs = [{"name": "SymPy", "github_orgs": ["sympy"], "participation": said}]
    checked = toolkit.check_participation(orgs, year=2027)
    assert checked[0]["participation"] == said


def test_the_body_search_finds_either_name_of_the_program() -> None:
    from git_into_gsoc.github.announcements import body_search_terms

    terms = " ".join(body_search_terms("2026-05-25"))
    assert '(gsoc OR "summer of code")' in terms and "in:body" in terms
    assert "updated:>=2026-05-25" in terms


def test_a_maintainer_naming_the_year_in_a_body_speaks_for_the_organization() -> None:
    from git_into_gsoc.github.announcements import reported_statements
    from git_into_gsoc.service import participation_from

    osm = _issue(
        "OpenStreetMap has not yet decided whether or not to participate in Google Summer of "
        "Code in 2027.",
        "2026-10-16",
        "MEMBER",
    )
    found = reported_statements([osm], year=2027)
    assert found[0]["status"] == "undecided" and found[0]["by_maintainer"]
    assert participation_from({"posts": found})["status"] == "undecided"


def test_a_quoted_statement_drops_markdown_link_syntax() -> None:
    from git_into_gsoc.github.announcements import reported_statements

    linked = _issue(
        "[It's likely that we will not participate in GSoC this year.]"
        "(https://web.archive.org/web/1/https://groups.google.com/g/x)",
        "2026-10-04",
    )
    quote = reported_statements([linked], year=2027)[0]["title"]
    assert quote == "It's likely that we will not participate in GSoC this year."
