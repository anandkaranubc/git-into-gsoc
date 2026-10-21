"""Every module imports on its own, so no import order hides a circular import."""

from __future__ import annotations

import importlib
import pkgutil
import sys

import pytest

import git_into_gsoc

MODULES = sorted(
    m.name for m in pkgutil.walk_packages(git_into_gsoc.__path__, prefix="git_into_gsoc.")
)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_first(name: str) -> None:
    saved = {k: v for k, v in sys.modules.items() if k.startswith("git_into_gsoc")}
    for key in saved:
        del sys.modules[key]
    try:
        importlib.import_module(name)
    finally:
        for key in [k for k in sys.modules if k.startswith("git_into_gsoc")]:
            del sys.modules[key]
        sys.modules.update(saved)
