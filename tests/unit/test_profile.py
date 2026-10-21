from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc.cli import app
from git_into_gsoc.progress.store import ProgressStore
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


def _archive_year(year: int) -> dict[str, Any]:
    orgs = []
    for raw in load_fixture("archive_organizations.json"):
        data = raw["years"].get(str(year))
        if data:
            orgs.append({**{k: v for k, v in raw.items() if k != "years"}, **data})
    return {"year": year, "organizations": orgs}


@pytest.fixture
def api() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        router.get(f"{ARCHIVE}/2026.json").mock(
            return_value=httpx.Response(200, json=_archive_year(2026))
        )
        router.get("https://api.github.com/search/issues").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        yield router


def test_profile_store_roundtrip() -> None:
    store = ProgressStore()
    store.set_profile(technologies=["Python", "rust"], interests=["science"], hours_per_week=12)
    profile = store.profile()
    assert profile["technologies"] == ["Python", "rust"]
    assert profile["hours_per_week"] == 12
    store.set_profile(timezone="Asia/Kolkata")
    assert store.profile()["technologies"] == ["Python", "rust"]
    assert store.profile()["timezone"] == "Asia/Kolkata"


def test_cli_profile_set_and_show() -> None:
    result = runner.invoke(
        app,
        [
            "profile",
            "--tech",
            "python, c++",
            "--interests",
            "science",
            "--hours",
            "10",
            "--tz",
            "UTC",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "python" in result.stdout and "c++" in result.stdout
    shown = runner.invoke(app, ["profile", "--output", "json"])
    assert shown.exit_code == 0
    assert '"hours_per_week": 10' in shown.stdout
    assert '"timezone": "UTC"' in shown.stdout


def test_cli_profile_empty_hint() -> None:
    result = runner.invoke(app, ["profile"])
    assert result.exit_code == 0
    assert "No profile saved" in result.stdout


def test_recommend_uses_saved_profile(api: respx.MockRouter) -> None:
    ProgressStore().set_profile(technologies=["python"], interests=["astronomy"])
    data = GSoCToolkit().recommend_path()
    assert data["technologies_used"] == ["python"]
    assert data["interests_used"] == ["astronomy"]
    assert data["recommended_orgs"][0]["name"] == "OpenAstronomy"
    assert data["profile_source"] == "saved profile"


def test_recommend_flags_override_and_persist(api: respx.MockRouter) -> None:
    ProgressStore().set_profile(technologies=["python"], interests=["astronomy"])
    data = GSoCToolkit().recommend_path(technologies=["c++"], interests=["radio"])
    assert data["technologies_used"] == ["c++"]
    assert data["profile_source"] == "flags"
    assert ProgressStore().profile()["technologies"] == ["c++"]
    assert ProgressStore().profile()["interests"] == ["radio"]


def test_recommend_without_anything_explains(api: respx.MockRouter) -> None:
    data = GSoCToolkit().recommend_path()
    assert data["technologies_used"] == []
    assert "profile" in data["evidence_note"].lower()
