"""`pointers` takes a GitLab issue link."""

from __future__ import annotations

import httpx
import respx

from git_into_gsoc.service import GSoCToolkit

API = "https://gitlab.gnome.org/api/v4/projects/GNOME%2Fgitg"


def test_pointers_accept_a_gitlab_issue_link() -> None:
    with respx.mock(assert_all_called=False) as api:
        api.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1550,
                    "default_branch": "master",
                    "web_url": "https://gitlab.gnome.org/GNOME/gitg",
                },
            )
        )
        api.get(f"{API}/issues/494").mock(
            return_value=httpx.Response(
                200,
                json={
                    "iid": 494,
                    "title": "Change the application ID suffix",
                    "description": "The suffix is set in `data/app.py`.",
                    "labels": [],
                    "web_url": "https://gitlab.gnome.org/GNOME/gitg/-/issues/494",
                },
            )
        )
        api.get(url__regex=rf"{API}/repository/tree\?.*path=data.*").mock(
            return_value=httpx.Response(200, json=[{"path": "data/app.py", "type": "blob"}])
        )
        api.get(url__regex=rf"{API}/repository/tree.*").mock(
            return_value=httpx.Response(200, json=[{"path": "data", "type": "tree"}])
        )
        api.get(url__regex=rf"{API}/repository/branches/.*").mock(
            return_value=httpx.Response(200, json={"commit": {"id": "f00"}})
        )
        data = GSoCToolkit().issue_pointers("https://gitlab.gnome.org/GNOME/gitg/-/issues/494")
    assert data["issue"]["repo"] == "gitlab.gnome.org/GNOME/gitg"
    assert data["files_likely_involved"][0]["path"] == "data/app.py"
    assert data["similar_fixes"] == [] and "No label" in data["similar_note"]
