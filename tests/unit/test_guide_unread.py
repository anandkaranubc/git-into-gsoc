"""A contributing guide GitHub did not send is unread, never "no guide"."""

from __future__ import annotations

import httpx
import pytest
import respx

from git_into_gsoc.drafts import render_draft
from git_into_gsoc.github.client import GitHubClient

API = "https://api.github.com/repos/acme/lib"
CONTRIBUTING = {"html_url": "https://github.com/acme/lib/blob/main/CONTRIBUTING.md"}
README = {"html_url": "https://github.com/acme/lib/blob/main/README.md"}


def _limited() -> httpx.Response:
    return httpx.Response(
        403, headers={"x-ratelimit-remaining": "0"}, json={"message": "API rate limit exceeded"}
    )


def _mock(**answers: httpx.Response) -> None:
    """Answer every read `contribution_guide` makes, except `answers`."""
    defaults = {
        "community/profile": httpx.Response(200, json={"files": {"contributing": CONTRIBUTING}}),
        "contents/CONTRIBUTING.md": httpx.Response(200, text="Comment on the issue first."),
        "contents/README.md": httpx.Response(200, text="# lib\n"),
    }
    respx.get(API).mock(return_value=httpx.Response(200, json={"full_name": "acme/lib"}))
    respx.get(f"{API}/contents/").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{API}/labels").mock(return_value=httpx.Response(200, json=[]))
    for path, response in {**defaults, **answers}.items():
        respx.get(f"{API}/{path}").mock(return_value=response)


@respx.mock
def test_a_guide_that_was_read_has_nothing_unread() -> None:
    _mock()
    guide = GitHubClient().contribution_guide("acme/lib")
    assert guide.unread == []
    assert guide.contributing_text == "Comment on the issue first."


@respx.mock
def test_a_rate_limited_profile_is_unread_not_no_guide() -> None:
    _mock(**{"community/profile": _limited()})
    guide = GitHubClient().contribution_guide("acme/lib")
    assert guide.unread == ["community profile"]
    assert any("GitHub did not answer for its community profile" in h for h in guide.setup_hints)
    assert not any("Read README.md before coding" in h for h in guide.setup_hints)


@respx.mock
def test_a_rate_limited_contributing_file_is_unread() -> None:
    _mock(**{"contents/CONTRIBUTING.md": _limited()})
    guide = GitHubClient().contribution_guide("acme/lib")
    assert guide.unread == ["contributing guide"]
    assert guide.contributing_url == CONTRIBUTING["html_url"]


@respx.mock
def test_a_rate_limited_readme_is_unread_when_there_is_no_contributing_file() -> None:
    _mock(
        **{
            "community/profile": httpx.Response(200, json={"files": {"readme": README}}),
            "contents/README.md": _limited(),
        }
    )
    guide = GitHubClient().contribution_guide("acme/lib")
    assert guide.unread == ["README"]


@respx.mock
def test_a_missing_contributing_file_is_an_answer() -> None:
    _mock(**{"contents/CONTRIBUTING.md": httpx.Response(404, json={})})
    guide = GitHubClient().contribution_guide("acme/lib")
    assert guide.unread == []
    assert guide.contributing_text == ""


def test_a_claim_rule_for_an_unread_guide_does_not_say_there_is_none() -> None:
    # Under a rate limit, `draft claim` said "no contributing guide found" for projects
    # that have one, right before a beginner claimed an issue.
    draft = render_draft(
        "claim", context={"claim_convention": {"kind": "unread", "text": "community profile"}}
    )
    rule = draft["rules"][0]
    assert rule["rule"].startswith("GitHub did not answer for this project's community profile")
    assert "no contributing guide" not in rule["rule"].lower()
    assert rule["source"] == "not read: GitHub did not answer"


def test_draft_claim_marks_the_rule_unread_when_the_guide_was_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from git_into_gsoc.models import ContributionGuide
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    unread = ContributionGuide(repo="acme/lib", unread=["community profile"])
    monkeypatch.setattr(toolkit.github, "contribution_guide", lambda repo: unread)
    monkeypatch.setattr(toolkit, "_add_pr_rules", lambda repo, context: None)
    draft = toolkit.draft("claim", repo="acme/lib")
    assert draft["context"]["claim_convention"]["kind"] == "unread"
    assert draft["rules"][0]["rule"].startswith("GitHub did not answer")


@respx.mock
def test_draft_pr_warns_when_the_guide_was_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # The sign-off and AI-disclosure lines come from the guide; unread, they were left
    # out with nothing said.
    from git_into_gsoc.models import ContributionGuide
    from git_into_gsoc.service import GSoCToolkit

    toolkit = GSoCToolkit()
    unread = ContributionGuide(repo="acme/lib", unread=["contributing guide"])
    monkeypatch.setattr(toolkit.github, "contribution_guide", lambda repo: unread)
    monkeypatch.setattr(toolkit, "_add_pr_rules", lambda repo, context: None)
    # Everything else a pr draft reads (metadata, branch rules, CI, manifests) is missing.
    respx.route(host="api.github.com").mock(return_value=httpx.Response(404, json={}))
    draft = toolkit.draft("pr", repo="acme/lib")
    assert "sign-off or AI-disclosure rule" in draft["warning"]
