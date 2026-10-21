"""Build an MCPB bundle (a zip the MCP registry and desktop hosts install) for this server.

The bundle uses the `uv` server type: it ships the project source and
pyproject.toml, and the host installs dependencies with uv. No virtual
environment is bundled, so the file stays small and works on every platform.

Usage: python scripts/build_mcpb.py [--out dist/git-into-gsoc.mcpb]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # overridden by --root
INCLUDE_FILES = ("pyproject.toml", "README.md", "LICENSE")
INCLUDE_TREES = ("src/git_into_gsoc", "skills/git-into-gsoc")
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}


def package_version(root: Path = ROOT) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.M)
    if not match:
        raise SystemExit("version not found in pyproject.toml")
    return match.group(1)


def manifest(version: str) -> dict[str, object]:
    return {
        "manifest_version": "0.4",
        "name": "git-into-gsoc",
        "display_name": "git-into-gsoc",
        "version": version,
        "description": (
            "Evidence-based Google Summer of Code preparation: organizations, repositories, "
            "free beginner issues, orientation, and proposals."
        ),
        "author": {
            "name": "git-into-gsoc contributors",
            "url": "https://github.com/anandkaranubc/git-into-gsoc",
        },
        "repository": {"type": "git", "url": "https://github.com/anandkaranubc/git-into-gsoc"},
        "homepage": "https://github.com/anandkaranubc/git-into-gsoc",
        "license": "MIT",
        "keywords": ["gsoc", "google-summer-of-code", "open-source", "onboarding", "github"],
        "server": {
            "type": "uv",
            "entry_point": "src/git_into_gsoc/mcp_server.py",
            "mcp_config": {
                "command": "uv",
                "args": ["run", "--directory", "${__dirname}", "git-into-gsoc", "mcp"],
                "env": {"GITHUB_TOKEN": "${user_config.github_token}"},
            },
        },
        "user_config": {
            "github_token": {
                "type": "string",
                "title": "GitHub token (optional)",
                "description": "Raises the GitHub API limit from 60 to 5,000 requests an hour. Public data only; no scopes needed.",
                "sensitive": True,
                "required": False,
            }
        },
        "compatibility": {
            "platforms": ["darwin", "linux", "win32"],
            "runtimes": {"python": ">=3.11"},
        },
    }


def bundle_files(root: Path = ROOT) -> list[Path]:
    files = [root / name for name in INCLUDE_FILES if (root / name).is_file()]
    for tree in INCLUDE_TREES:
        for path in sorted((root / tree).rglob("*")):
            if path.is_file() and not (EXCLUDE_PARTS & set(path.parts)):
                files.append(path)
    return files


def build(out: Path, root: Path = ROOT) -> tuple[Path, str]:
    version = package_version(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest(version), indent=2) + "\n")
        for path in bundle_files(root):
            zf.write(path, path.relative_to(root).as_posix())
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    return out, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "git-into-gsoc.mcpb")
    parser.add_argument("--manifest-only", action="store_true", help="Print manifest.json and exit")
    parser.add_argument("--root", type=Path, default=ROOT, help="Source checkout to bundle (default: this repository)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.manifest_only:
        print(json.dumps(manifest(package_version(root)), indent=2))
        return 0
    path, digest = build(args.out, root)
    print(f"{path} sha256={digest} size={path.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
