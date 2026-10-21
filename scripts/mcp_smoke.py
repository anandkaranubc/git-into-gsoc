"""Start an MCP server the way an assistant does and check that it answers.

This speaks the Model Context Protocol over stdio with nothing but the standard
library: it sends `initialize`, lists the tools, prompts, and resources, and
calls one tool that needs no network. It works with any launch command, so it
checks the exact command a plugin, extension, or config file ships.

Usage:
    python scripts/mcp_smoke.py [--timeout 120] [--json] [--cwd DIR] -- COMMAND [ARGS...]

Examples:
    python scripts/mcp_smoke.py -- git-into-gsoc mcp
    python scripts/mcp_smoke.py -- uvx --from . git-into-gsoc mcp

The server's progress and cache folders point at a temporary directory, so a
check never writes to your real progress file. Exit status 0 means every step
passed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
OFFLINE_TOOL = ("gsoc_journey_guide", {"phase": "learn"})
MIN_TOOLS = 20


class SmokeError(RuntimeError):
    """A step failed; the message says which one and why."""


class StdioPeer:
    """A tiny JSON-RPC client over a child process's stdin and stdout."""

    def __init__(self, argv: list[str], env: dict[str, str], cwd: str | None = None) -> None:
        self.process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._stderr: list[str] = []
        self._next_id = 0
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _pump_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr.append(line.rstrip("\n"))

    def stderr_tail(self, lines: int = 15) -> str:
        return "\n".join(self._stderr[-lines:])

    def send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SmokeError(f"the server closed its input ({exc})") from exc

    def request(self, method: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SmokeError(f"{method}: no answer within {timeout:.0f}s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                code = self.process.poll()
                raise SmokeError(f"{method}: the server exited (status {code}) before answering")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                # Anything that is not JSON on stdout breaks every MCP client.
                raise SmokeError(
                    f"the server printed non-protocol text on stdout: {line[:200]!r}"
                ) from exc
            if message.get("id") != request_id or "method" in message:
                continue  # a notification or a request from the server
            if "error" in message:
                raise SmokeError(f"{method}: error {message['error']}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise SmokeError(f"{method}: the answer has no result object")
            return result

    def close(self) -> None:
        if self.process.stdin:
            with contextlib.suppress(OSError):
                self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)


def smoke(
    argv: list[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run every step against ``argv``. Returns a summary; raises SmokeError on failure."""
    with tempfile.TemporaryDirectory(prefix="gig-smoke-") as scratch:
        child_env = dict(os.environ if env is None else env)
        child_env.setdefault("GIG_DATA_DIR", str(Path(scratch) / "data"))
        child_env.setdefault("GIG_CACHE_DIR", str(Path(scratch) / "cache"))
        started = time.monotonic()
        try:
            peer = StdioPeer(argv, child_env, cwd)
        except OSError as exc:
            raise SmokeError(f"could not start {argv[0]!r}: {exc}") from exc
        try:
            info = peer.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "git-into-gsoc-smoke", "version": "1"},
                },
                timeout,
            )
            ready = time.monotonic() - started
            peer.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            step = min(timeout, 60.0)
            tools = peer.request("tools/list", {}, step).get("tools", [])
            prompts = peer.request("prompts/list", {}, step).get("prompts", [])
            resources = peer.request("resources/list", {}, step).get("resources", [])
            name, arguments = OFFLINE_TOOL
            called = peer.request("tools/call", {"name": name, "arguments": arguments}, step)
        except SmokeError as exc:
            tail = peer.stderr_tail()
            raise SmokeError(f"{exc}\n--- server stderr ---\n{tail}" if tail else str(exc)) from exc
        finally:
            peer.close()
    names = sorted(t.get("name", "") for t in tools)
    if len(names) < MIN_TOOLS:
        raise SmokeError(f"expected at least {MIN_TOOLS} tools, got {len(names)}: {names}")
    if name not in names:
        raise SmokeError(f"{name} is not among the tools")
    if called.get("isError"):
        raise SmokeError(f"{name} returned an error: {called.get('content')}")
    text = "".join(c.get("text", "") for c in called.get("content", []) if isinstance(c, dict))
    if "learn" not in text:
        raise SmokeError(f"{name} answered without the phase it was asked for: {text[:200]!r}")
    server = info.get("serverInfo", {})
    return {
        "command": argv,
        "server": server.get("name"),
        "version": server.get("version"),
        "protocol": info.get("protocolVersion"),
        "startup_seconds": round(ready, 2),
        "tools": len(names),
        "prompts": len(prompts),
        "resources": len(resources),
        "instructions": bool(info.get("instructions")),
    }


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start an MCP server the way an assistant does and check that it answers."
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="Seconds to wait for startup")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON")
    parser.add_argument("--cwd", help="Folder to start the server in (as a client would)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- COMMAND [ARGS...]")
    ns = parser.parse_args(args)
    argv = ns.command[1:] if ns.command[:1] == ["--"] else ns.command
    if not argv:
        parser.error("give the server command after --")
    try:
        summary = smoke(argv, timeout=ns.timeout, cwd=ns.cwd)
    except SmokeError as exc:
        print(f"MCP smoke check failed for: {' '.join(argv)}\n{exc}", file=sys.stderr)
        return 1
    if ns.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"ok: {summary['server']} {summary['version']} answered in "
            f"{summary['startup_seconds']}s with {summary['tools']} tools, "
            f"{summary['prompts']} prompts, {summary['resources']} resources "
            f"(protocol {summary['protocol']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
