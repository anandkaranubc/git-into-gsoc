"""`orgs` with no filters ranks by the saved profile, and says so."""

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

OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


@pytest.fixture
def api() -> Any:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{OFFICIAL}/2027/organizations/").mock(return_value=httpx.Response(404))
        router.get(f"{OFFICIAL}/2026/organizations/").mock(
            return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
        )
        router.get(f"{ARCHIVE}/organizations.json").mock(
            return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
        )
        yield router


def test_orgs_without_filters_use_the_saved_profile(api: Any) -> None:
    ProgressStore().set_profile(technologies=["python"], interests=["astronomy"])
    data = GSoCToolkit().match_orgs()
    assert data["matched_on"] == {
        "technologies": ["python"],
        "topics": ["astronomy"],
        "from_profile": True,
    }
    assert data["organizations"][0]["name"] == "OpenAstronomy"
    explicit = GSoCToolkit().match_orgs(technologies=["c++"])
    assert explicit["matched_on"]["from_profile"] is False


def test_orgs_without_a_profile_browse_and_the_cli_says_what_it_matched(api: Any) -> None:
    assert GSoCToolkit().match_orgs()["matched_on"]["from_profile"] is False
    ProgressStore().set_profile(technologies=["python"], interests=["astronomy"])
    result = CliRunner().invoke(app, ["orgs", "-n", "3"])
    assert result.exit_code == 0, result.output
    assert "Matching your saved profile: python; astronomy" in result.output
