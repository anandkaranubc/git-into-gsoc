"""Sandboxed assistants may forbid writing outside the project; reading must still work."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from git_into_gsoc import config
from git_into_gsoc.cli import app
from git_into_gsoc.errors import InputError
from git_into_gsoc.http_client import CachedHttpClient
from git_into_gsoc.progress.store import ProgressStore

runner = CliRunner()

needs_posix_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions and a non-root user"
)


@pytest.fixture
def locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cache and data folders inside a folder nobody may write to."""
    root = tmp_path / "read-only"
    root.mkdir()
    monkeypatch.setenv("GIG_CACHE_DIR", str(root / "cache"))
    monkeypatch.setenv("GIG_DATA_DIR", str(root / "data"))
    config.get_settings.cache_clear()
    root.chmod(stat.S_IRUSR | stat.S_IXUSR)
    yield root
    root.chmod(stat.S_IRWXU)
    config.get_settings.cache_clear()


@needs_posix_permissions
def test_the_http_client_runs_without_a_cache(locked: Path) -> None:
    client = CachedHttpClient()
    assert client.cache_size_bytes() == 0
    assert not (locked / "cache").exists()


@needs_posix_permissions
def test_progress_reads_but_explains_why_it_cannot_save(locked: Path) -> None:
    store = ProgressStore()
    assert store.load().shortlisted_orgs == []
    with pytest.raises(InputError) as caught:
        store.shortlist_org("SymPy")
    assert "Cannot save your progress" in str(caught.value)
    assert caught.value.hint and "GIG_DATA_DIR" in caught.value.hint


@needs_posix_permissions
def test_doctor_reports_an_unwritable_folder_instead_of_crashing(locked: Path) -> None:
    with respx.mock:
        respx.route().mock(
            return_value=httpx.Response(200, json={"resources": {"core": {"limit": 60}}})
        )
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "cannot be written" in result.stdout
    assert "Traceback" not in result.output


def test_doctor_without_an_assistant_does_not_look_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Yellow "MCP registered in: nowhere yet" read like an error in a terminal-only setup.
    monkeypatch.setenv("GIG_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIG_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("GIG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    with respx.mock:
        respx.route().mock(
            return_value=httpx.Response(200, json={"resources": {"core": {"limit": 60}}})
        )
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    words = " ".join(result.stdout.split())
    assert "AI assistants connected: none yet. That is fine in a terminal" in words
    assert "nowhere" not in words


def test_setup_without_any_assistant_does_not_say_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIG_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0, result.output
    words = " ".join(result.stdout.split())
    assert "No AI assistant was found, so only the skill was copied to" in words
    assert "Restart your assistant" not in result.stdout
    # A blind beginner install read these as errors; with no assistant they say nothing useful.
    assert "No AI assistant detected" not in words
    assert "MCP command" not in words
    assert "Setup complete" not in words
    # With --no-skill nothing is copied, so the short message would be false.
    bare = runner.invoke(app, ["setup", "--no-skill"])
    assert bare.exit_code == 0, bare.output
    assert "only the skill was copied" not in " ".join(bare.stdout.split())


def test_setup_with_an_assistant_suggests_a_natural_first_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIG_HOME", str(tmp_path / "home"))
    result = runner.invoke(app, ["setup", "--assistant", "cursor"])
    assert result.exit_code == 0, result.output
    assert "Restart your assistant" in result.stdout
    assert "Where do I start?" in result.stdout
