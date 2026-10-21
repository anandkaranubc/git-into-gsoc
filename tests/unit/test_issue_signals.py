"""Issues filed by maintainers carry a visible signal and a small bonus."""

from __future__ import annotations

from git_into_gsoc.github.client import _candidate_from_search
from git_into_gsoc.scoring.issues import score_issue


def _item(association: str) -> dict[str, object]:
    return {
        "id": 1,
        "number": 7,
        "title": "Fix the thing",
        "html_url": "https://github.com/o/r/issues/7",
        "repository_url": "https://api.github.com/repos/o/r",
        "labels": [{"name": "good first issue"}],
        "user": {"login": "maintainer"},
        "author_association": association,
        "body": "",
    }


def test_maintainer_filed_issue_is_flagged_and_scored() -> None:
    member = _candidate_from_search(_item("MEMBER"))
    outsider = _candidate_from_search(_item("NONE"))
    assert member is not None and outsider is not None
    assert member.filed_by_maintainer and not outsider.filed_by_maintainer
    scored = score_issue(member)
    assert scored.beginner_score > score_issue(outsider).beginner_score
    assert any("Filed by a maintainer" in s for s in scored.signals)
