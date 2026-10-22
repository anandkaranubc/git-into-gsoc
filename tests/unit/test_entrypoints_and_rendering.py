"""Entry points and rendering: `python -m`, the snapshot writer, tables and panels from fixture
data, Windows code pages, and files saved by editors."""

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


def test_an_unchanged_refresh_leaves_the_snapshot_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The weekly workflow opens a pull request on any diff, so order and date must not churn."""
    from datetime import UTC, datetime

    archive = load_fixture("archive_organizations.json")
    official = load_fixture("official_orgs_2026.json")
    paths = snapshot.write_snapshot(archive=archive, official=official, year=2026, out=tmp_path)
    first = [p.read_bytes() for p in paths]

    class NextWeek(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return datetime(2030, 1, 7, tzinfo=UTC)

    monkeypatch.setattr(snapshot, "datetime", NextWeek)
    snapshot.write_snapshot(
        archive=archive, official=list(reversed(official)), year=2026, out=tmp_path
    )
    assert [p.read_bytes() for p in paths] == first
    snapshot.write_snapshot(archive=archive, official=official[1:], year=2026, out=tmp_path)
    changed = json.loads(paths[1].read_text(encoding="utf-8"))
    assert (
        changed["generated"] == "2030-01-07" and len(changed["organizations"]) == len(official) - 1
    )


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
    respx.get(url__startswith="https://api.github.com/").mock(return_value=httpx.Response(503))
    result = runner.invoke(app, ["orgs", "--tech", "python", "--topics", "science", "-n", "3"])
    assert result.exit_code == 0, result.output
    assert "snapshot" in result.output
    assert "Skill Python: tech tag 'python'" in result.output  # evidence, with its source
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
    result = runner.invoke(app, ["repo", "acme/lib", "--track"])
    assert result.exit_code == 0, result.output
    assert "grade" in result.output and "CONTRIBUTING" in result.output
    assert "Dev container" in result.output
    assert "Discord" in result.output
    words = " ".join(result.output.split())
    # A blind beginner run could not see where a C's points went: signals with no
    # line of their own (Code of Conduct, templates) cost points silently.
    assert "Where it lost points" in words
    assert "Code of Conduct: 0 of 4" in words
    assert "Issue or PR templates: 0 of 4" in words
    # Missing ecosyste.ms data is left out with a reason, never shown with a check mark.
    assert "Left out: people who landed a single commit last year" in words
    assert "✓ No commit history" not in words
    assert "Saved to your progress. `next` will list new beginner issues opened here." in words
    # Like the other commands, `repo` ends with what to run next.
    assert "Next: git-into-gsoc " in words


@respx.mock
def test_setup_hints_never_name_a_guide_the_repository_lacks() -> None:
    # "Read README.md and CONTRIBUTING.md" right after "No CONTRIBUTING guide detected"
    # read as a contradiction in a blind beginner run (2026-10-22).
    from git_into_gsoc.service import GSoCToolkit

    api = "https://api.github.com/repos/acme/bare"
    respx.get(api).mock(return_value=httpx.Response(200, json={"language": None}))
    respx.get(f"{api}/community/profile").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{api}/contents/").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{api}/labels").mock(return_value=httpx.Response(200, json=[]))
    guide = GSoCToolkit().github.contribution_guide("acme/bare")
    assert guide.setup_hints == ["Read README.md before coding"]


def test_output_never_crashes_on_a_legacy_windows_code_page(tmp_path: Path) -> None:
    """Piped output on Windows uses cp1252, which has no ☐ (printed by `proposal`)."""
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "PYTHONIOENCODING": "cp1252",
        "PYTHONUTF8": "0",
        "GIG_DATA_DIR": str(tmp_path / "data"),
        "GIG_CACHE_DIR": str(tmp_path / "cache"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "git_into_gsoc", "proposal"],
        capture_output=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode("cp1252", "replace")[-600:]
    assert "? " in result.stdout.decode("cp1252")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "cp1252"])
def test_proposal_reads_drafts_saved_by_any_common_editor(tmp_path: Path, encoding: str) -> None:
    from git_into_gsoc.cli import app

    draft = tmp_path / "draft.md"
    # The heading is on the first line, where a byte-order mark would hide it.
    draft.write_text("## About me\nCafé owner — I like parsers.\n", encoding=encoding)
    result = CliRunner().invoke(app, ["proposal", str(draft), "--no-verify", "--output", "json"])
    assert result.exit_code == 0, result.output[-600:]
    findings = {f["id"]: f["status"] for f in json.loads(result.output)["findings"]}
    assert findings["about"] == "pass"


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "cp1252"])
def test_draft_check_reads_messages_saved_by_any_common_editor(
    tmp_path: Path, encoding: str
) -> None:
    from git_into_gsoc.cli import app

    message = tmp_path / "message.txt"
    message.write_text("Café question — where is the parser?\n", encoding=encoding)
    result = CliRunner().invoke(
        app, ["draft", "question", "--check", str(message), "--output", "json"]
    )
    assert result.exit_code == 0, result.output[-600:]
    assert json.loads(result.output)["words"] == 6
