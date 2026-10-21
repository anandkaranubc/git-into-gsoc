"""Write the plugin and extension manifests from one definition.

The values live in ``src/git_into_gsoc/install/distribution.py``. Run this after
changing them; ``--check`` (used by the tests) fails when a committed file differs
from what would be written, and names the file.

Usage: python scripts/sync_integrations.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from git_into_gsoc import __version__  # noqa: E402
from git_into_gsoc.install.distribution import manifests  # noqa: E402


def rendered() -> dict[Path, str]:
    return {
        ROOT / rel: json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        for rel, data in manifests(__version__).items()
    }


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
