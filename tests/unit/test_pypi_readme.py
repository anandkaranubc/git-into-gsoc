"""The PyPI page is README.md with its relative paths rewritten (see pyproject.toml).

PyPI shows the README without the rest of the repository, so a relative image is a
broken picture there and a relative link is a 404. These tests apply the same
substitutions the build applies (hatch-fancy-pypi-readme runs ``re.sub`` with each
pattern in order) and check what PyPI would get.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = "https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/"
BLOB = "https://github.com/anandkaranubc/git-into-gsoc/blob/main/"

IMAGE = re.compile(r'(?:src|srcset)="([^"]+)"|!\[[^\]]*\]\(([^)\s]+)\)')
LINK = re.compile(r'href="([^"]+)"|(?<!!)\[[^\]]*\]\(([^)\s]+)\)')
ABSOLUTE = re.compile(r"(?:https?:|mailto:|#)")


def _pypi_description() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    hook = pyproject["tool"]["hatch"]["metadata"]["hooks"]["fancy-pypi-readme"]
    assert "readme" in pyproject["project"]["dynamic"]
    text = "".join((ROOT / f["path"]).read_text(encoding="utf-8") for f in hook["fragments"])
    for sub in hook["substitutions"]:
        flags = re.IGNORECASE if sub.get("ignore-case") else 0
        text = re.sub(sub["pattern"], sub["replacement"], text, flags=flags)
    return text


def _targets(pattern: re.Pattern[str], text: str) -> list[str]:
    return [a or b for a, b in pattern.findall(text)]


def _relative(text: str) -> list[str]:
    return [t for t in _targets(IMAGE, text) + _targets(LINK, text) if not ABSOLUTE.match(t)]


def test_the_readme_uses_relative_paths_that_need_rewriting() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert _relative(readme), "nothing to rewrite; the substitutions may no longer be needed"


def test_the_pypi_page_has_no_relative_images_or_links() -> None:
    assert _relative(_pypi_description()) == []


def test_rewritten_paths_exist_in_the_repository() -> None:
    text = _pypi_description()
    for target in _targets(IMAGE, text):
        if target.startswith(RAW):
            assert (ROOT / target.removeprefix(RAW)).is_file(), target
    for target in _targets(LINK, text):
        if target.startswith(BLOB):
            path = target.removeprefix(BLOB).split("#", 1)[0]
            assert (ROOT / path).exists(), target


def test_images_point_at_raw_files_and_links_at_github() -> None:
    text = _pypi_description()
    assert f'src="{RAW}brand/readme/banner-light.svg"' in text
    assert f'href="{BLOB}LICENSE"' in text
    assert f"]({BLOB}docs/README.md)" in text
    assert "](https://docs.astral.sh/uv/)" in text  # absolute links are left alone


def test_the_mcp_registry_marker_survives() -> None:
    # The MCP registry looks for this line in the PyPI description before it accepts a
    # PyPI package for the server.
    assert "mcp-name: io.github.anandkaranubc/git-into-gsoc" in _pypi_description()
