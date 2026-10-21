"""A program in the current folder, often a cloned repository, must never run."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from git_into_gsoc import config
from git_into_gsoc.programs import find_program

NAME = "gh"


def _plant(folder: Path, marker: Path) -> Path:
    """An executable `gh` that records it ran, in the form the platform runs."""
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        script = folder / f"{NAME}.bat"
        script.write_text(f'@echo off\r\necho ran> "{marker}"\r\necho planted-token\r\n')
    else:
        script = folder / NAME
        script.write_text(f'#!/bin/sh\necho ran > "{marker}"\necho planted-token\n')
        script.chmod(0o755)
    return script


def test_a_program_in_the_current_folder_is_never_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "cloned-repo"
    _plant(repo, tmp_path / "ran")
    monkeypatch.chdir(repo)
    # ".", "", and a relative entry all point into the current folder; so does its own path.
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "bin", str(repo)]))
    assert find_program(NAME) is None


def test_a_program_elsewhere_on_path_is_still_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "tools"
    real = _plant(tools, tmp_path / "ran")
    repo = tmp_path / "cloned-repo"
    _plant(repo, tmp_path / "ran-planted")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(tools)]))
    found = find_program(NAME)
    assert found is not None and Path(found).resolve().parent == real.parent.resolve()


def test_the_token_lookup_never_runs_a_planted_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "ran"
    repo = tmp_path / "cloned-repo"
    _plant(repo, marker)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", os.pathsep.join([".", os.environ.get("PATH", "")]))
    monkeypatch.setenv("GIG_USE_GH_CLI", "true")
    config.get_settings.cache_clear()
    config._gh_cli_token.cache_clear()
    token, _source = config.resolve_token(config.Settings())
    assert not marker.exists(), "a gh script from the current folder ran"
    assert token != "planted-token"
