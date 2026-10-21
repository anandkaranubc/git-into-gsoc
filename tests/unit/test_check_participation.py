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
    checked = toolkit.check_participation(ORGS[:2], year=2027, check=1)
    assert checked[0]["participation"] == {"status": "unknown"}
    assert "participation" not in checked[1]  # only the first `check` are looked at
