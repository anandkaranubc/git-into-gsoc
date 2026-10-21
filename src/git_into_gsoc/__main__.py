"""python -m git_into_gsoc"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        from git_into_gsoc.mcp_server import main as mcp_main

        mcp_main()
        return
    from git_into_gsoc.cli import app

    app()


if __name__ == "__main__":
    main()
