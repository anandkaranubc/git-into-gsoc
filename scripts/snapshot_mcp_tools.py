"""Save the MCP server's `tools/list` answer for the plugin eval mocks.

`claude plugin eval` answers tool calls from ``plugin-evals/mocks/git-into-gsoc/*.md``
and reads ``_tools.json`` beside them for the real tool descriptions and input schemas,
so the model under test reads the same tool text an assistant does. Run this after
changing a tool docstring or signature in ``mcp_server.py``;
``tests/unit/test_plugin_evals.py`` fails while the file is stale.

Usage: python scripts/snapshot_mcp_tools.py [-- COMMAND [ARGS...]]

The default command is ``git-into-gsoc mcp``; pass another to snapshot a different
build. The server is started over stdio like an assistant starts it, with its progress
and cache folders pointed at a temporary directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_smoke import PROTOCOL_VERSION, SmokeError, StdioPeer

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "plugin-evals" / "mocks" / "git-into-gsoc" / "_tools.json"


def list_tools(argv: list[str], timeout: float) -> list[dict[str, object]]:
    """The `tools/list` result of the server started with ``argv``."""
    with tempfile.TemporaryDirectory(prefix="gig-tools-") as scratch:
        env = dict(os.environ)
        env.setdefault("GIG_DATA_DIR", str(Path(scratch) / "data"))
        env.setdefault("GIG_CACHE_DIR", str(Path(scratch) / "cache"))
        peer = StdioPeer(argv, env)
        try:
            peer.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "git-into-gsoc-snapshot", "version": "1"},
                },
                timeout,
            )
            peer.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = peer.request("tools/list", {}, timeout).get("tools", [])
        finally:
            peer.close()
    return [t for t in tools if isinstance(t, dict)]


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("command", nargs="*", help="Server command (default: git-into-gsoc mcp)")
    ns = parser.parse_args(args)
    argv = ns.command or ["git-into-gsoc", "mcp"]
    try:
        tools = list_tools(argv, ns.timeout)
    except (SmokeError, OSError) as exc:
        print(f"could not list the tools: {exc}", file=sys.stderr)
        return 1
    TARGET.write_text(json.dumps({"tools": tools}, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
