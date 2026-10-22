"""`org` speaks plainly: channel names a person would use, and a next step at the end."""

from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from git_into_gsoc.cli import _channel_label, app


def test_channel_kinds_read_as_words() -> None:
    assert _channel_label("mailingList") == "Mailing list"
    assert _channel_label("chat") == "Chat"
    assert _channel_label("someNewKind") == "Some new kind"


def test_org_shows_plain_channels_and_a_next_step(monkeypatch: Any) -> None:
    # ML4SCI (blind beginner test, 2026-10-22) printed "mailingList:" and "chat:", and the
    # output stopped at the projects table with no next step.
    from git_into_gsoc import cli

    data = {
        "found": True,
        "catalog": {"year": 2026},
        "gsoc_posts": {},
        "organization": {
            "name": "ML4SCI",
            "description": "Machine learning applications in science",
            "url": "https://ml4sci.org/",
            "github_orgs": ["ML4SCI"],
            "channels": [
                {"kind": "mailingList", "value": "ml4-sci@cern.ch"},
                {"kind": "chat", "value": "https://app.gitter.im/#/room/#ML4SCI_general:gitter.im"},
            ],
            "technologies": ["python"],
            "topics": ["physics"],
            "projects_by_year": {"2026": 33},
            "official": True,
            "recent_projects": [{"year": 2026, "title": "DeepLense"}],
        },
    }

    class Fake:
        def org_details(self, *a: Any, **k: Any) -> dict[str, Any]:
            return data

    monkeypatch.setattr(cli, "_toolkit", lambda: Fake())
    result = CliRunner().invoke(app, ["org", "ML4SCI"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    assert "Mailing list: ml4-sci@cern.ch" in result.output
    assert "Chat: https://app.gitter.im" in result.output
    assert "mailingList" not in result.output and "chat:" not in result.output
    assert 'Next: git-into-gsoc ideas "ML4SCI"' in result.output
