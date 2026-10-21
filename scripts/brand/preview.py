"""Stage the website the way GitHub Pages serves it, then serve it locally.

    python -m scripts.brand.preview            # http://127.0.0.1:8765
    python -m scripts.brand.preview --stage-only --out /tmp/gig-site

The page lives in ``site/`` and references the generated assets at ``brand/``,
so staging copies both into one directory (the Pages workflow does the same).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def stage(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "site", out)
    shutil.copytree(ROOT / "brand", out / "brand")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "git-into-gsoc-site")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--stage-only", action="store_true")
    args = ap.parse_args()
    out = stage(args.out)
    print(f"staged site at {out}")
    if args.stage_only:
        return
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
        print(f"serving http://127.0.0.1:{args.port}/  (ctrl-c to stop)")
        srv.serve_forever()


if __name__ == "__main__":
    main()
