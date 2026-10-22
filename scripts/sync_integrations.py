"""Write the plugin and extension manifests and the install links from one definition.

The values live in ``src/git_into_gsoc/install/distribution.py``. The install
buttons in README.md and docs/assistants.md, and the one-click links on the project
site, sit between generated-block markers.
Run this after changing any of them; ``--check`` (used by the tests) fails when a committed file differs
from what would be written, and names the file.

Usage: python scripts/sync_integrations.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from git_into_gsoc import __version__  # noqa: E402
from git_into_gsoc.install.distribution import (  # noqa: E402
    install_badges,
    manifests,
    site_install_links,
)


def _block(name: str) -> re.Pattern[str]:
    """A generated block inside a hand-written page, between two markers."""
    return re.compile(rf"(<!-- generated:{name} -->\n).*?(<!-- /generated:{name} -->)", re.S)


# page -> (block name, what goes in it)
PAGES_WITH_LINKS = {
    "README.md": ("install-links", install_badges),
    "docs/assistants.md": ("install-links", install_badges),
    "site/index.html": ("site-install-links", site_install_links),
}


def rendered() -> dict[Path, str]:
    files = {
        ROOT / rel: json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        for rel, data in manifests(__version__).items()
    }
    for rel, (name, content) in PAGES_WITH_LINKS.items():
        page = ROOT / rel
        text = page.read_text(encoding="utf-8")
        match = _block(name).search(text)
        if not match:
            raise SystemExit(f"{rel} has no <!-- generated:{name} --> block")
        files[page] = text[: match.end(1)] + content() + "\n" + text[match.start(2) :]
    return files


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the plugin and extension manifests.")
    parser.add_argument("--check", action="store_true", help="Only report files that differ")
    ns = parser.parse_args(args)
    stale = []
    for path, text in rendered().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT).as_posix())
        if not ns.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if ns.check and stale:
        print(
            "These files differ from src/git_into_gsoc/install/distribution.py:\n  "
            + "\n  ".join(stale)
            + "\nRun: python scripts/sync_integrations.py",
            file=sys.stderr,
        )
        return 1
    for name in stale:
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
