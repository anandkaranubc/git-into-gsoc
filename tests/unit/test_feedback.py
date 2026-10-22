"""The feedback links: what they prefill, and that nothing is sent."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from typer.testing import CliRunner

from git_into_gsoc import __version__
from git_into_gsoc.cli import app
from git_into_gsoc.feedback import FORMS, form_url

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_the_link_fills_in_versions_and_nothing_personal() -> None:
    url = form_url("feedback")
    query = parse_qs(urlparse(url).query)
    assert query["template"] == ["feedback.yml"]
    assert __version__ in query["setup"][0]
    assert str(Path.home()) not in url


def test_every_form_and_field_the_links_use_exists() -> None:
    for template, field in FORMS.values():
        text = (ROOT / ".github" / "ISSUE_TEMPLATE" / template).read_text(encoding="utf-8")
        assert field in re.findall(r"^\s+id:\s*(\S+)\s*$", text, flags=re.M), template


def test_feedback_prints_the_link_without_opening_anything() -> None:
    result = runner.invoke(app, ["feedback", "--no-open"])
    assert result.exit_code == 0, result.output
    assert "Nothing is sent until you read it" in " ".join(result.stdout.split())
    assert "issues/new?template=feedback.yml" in result.stdout
    bug = runner.invoke(app, ["feedback", "--bug", "--no-open"])
    assert "template=bug_report.yml" in bug.stdout
