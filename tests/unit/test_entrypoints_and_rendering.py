from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from conftest import load_fixture
from git_into_gsoc import __main__ as entry
from git_into_gsoc.cli import app
from git_into_gsoc.gsoc import snapshot

runner = CliRunner()
OFFICIAL = "https://summerofcode.withgoogle.com/api/program"
ARCHIVE = "https://api.gsocorganizations.dev"


def test_python_m_dispatches_to_the_cli(monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("sys.argv", ["git-into-gsoc", "journey", "--output", "json"])
    with pytest.raises(SystemExit) as exit_info:
        entry.main()
    assert exit_info.value.code in (0, None)
    assert "learn" in capsys.readouterr().out


def test_snapshot_writer_round_trips(tmp_path: Path) -> None:
    archive = load_fixture("archive_organizations.json")
    official = load_fixture("official_orgs_2026.json")
    history_path, official_path = snapshot.write_snapshot(
        archive=archive, official=official, year=2026, out=tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    compact = json.loads(official_path.read_text(encoding="utf-8"))
    assert history["organizations"]["SymPy"]["years"]["2026"]["num_projects"] >= 1
    assert compact["year"] == 2026 and len(compact["organizations"]) == len(official)
    assert "logo_url" not in compact["organizations"][0]


@respx.mock
def test_snapshot_refresh_command_writes_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(f"{OFFICIAL}/2026/organizations/").mock(
        return_value=httpx.Response(200, json=load_fixture("official_orgs_2026.json"))
    )
    respx.get(f"{ARCHIVE}/organizations.json").mock(
        return_value=httpx.Response(200, json=load_fixture("archive_organizations.json"))
    )
    monkeypatch.setattr(snapshot, "_data_dir", lambda: tmp_path)
    assert snapshot.main(["2026"]) == 0
    assert (tmp_path / snapshot.HISTORY_FILE).is_file()
    assert (tmp_path / snapshot.OFFICIAL_FILE).is_file()
    respx.get(f"{OFFICIAL}/2031/organizations/").mock(return_value=httpx.Response(404))
    assert snapshot.main(["2031"]) == 1


@respx.mock
def test_orgs_table_renders_from_the_embedded_snapshot() -> None:
    respx.get(url__startswith=OFFICIAL).mock(return_value=httpx.Response(503))
    respx.get(url__startswith=ARCHIVE).mock(return_value=httpx.Response(503))
    result = runner.invoke(app, ["orgs", "--tech", "python", "--topics", "science", "-n", "3"])
    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output
    assert "Uses python" in result.output
    detail = runner.invoke(app, ["org", "SymPy"])
    assert detail.exit_code == 0, detail.output
    assert "Ideas:" in detail.output


@respx.mock
def test_repo_panel_renders_signals_and_setup_hints() -> None:
    api = "https://api.github.com/repos/acme/lib"
    respx.get(api).mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "acme/lib",
                "html_url": "https://github.com/acme/lib",
                "pushed_at": "2026-10-20T00:00:00Z",
                "stargazers_count": 300,
                "license": {"spdx_id": "MIT"},
            },
        )
    )
    respx.get(f"{api}/community/profile").mock(
        return_value=httpx.Response(
            200,
            json={
                "files": {
                    "contributing": {
                        "html_url": "https://github.com/acme/lib/blob/main/CONTRIBUTING.md"
                    }
                }
            },
        )
    )
    respx.get(f"{api}/actions/workflows").mock(
        return_value=httpx.Response(200, json={"total_count": 1})
    )
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/assignees").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/pulls").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/issues/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/pulls/comments").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/contents/").mock(
        return_value=httpx.Response(
            200, json=[{"name": "pyproject.toml"}, {"name": ".devcontainer"}]
        )
    )
    respx.get(f"{api}/contents/CONTRIBUTING.md").mock(
        return_value=httpx.Response(200, text="Join us on Discord. Run pre-commit.")
    )
    respx.get(url__startswith="https://commits.ecosyste.ms").mock(
        return_value=httpx.Response(404, json={})
    )
    result = runner.invoke(app, ["repo", "acme/lib"])
    assert result.exit_code == 0, result.output
    assert "grade" in result.output and "CONTRIBUTING" in result.output
    assert "Dev container" in result.output
    assert "Discord" in result.output
