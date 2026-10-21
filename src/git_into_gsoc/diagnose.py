"""Name the likely cause of a failed setup or test run from its output.

Environment setup is the most common first barrier for newcomers. A beginner
pastes the error into a search engine and gets a dozen guesses. This module
matches the output against a small set of well-known failure shapes, quotes the
line that matched, says what it usually means and what to try, and (when the
caller passes the project's CI environment) compares it with what CI sets up.
It never runs anything. Idea from ContribOS's `setup --diagnose` (MIT); the
patterns and advice here are written for this project.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from git_into_gsoc.text import clean_untrusted


@dataclass(frozen=True)
class Pattern:
    id: str
    regex: re.Pattern[str]
    means: str
    try_: tuple[str, ...]


def _p(id_: str, pattern: str, means: str, *try_: str) -> Pattern:
    return Pattern(id_, re.compile(pattern, re.I | re.M), means, tuple(try_))


PATTERNS: tuple[Pattern, ...] = (
    _p(
        "missing_module",
        r"ModuleNotFoundError: No module named '([\w.]+)'|ImportError: cannot import name|"
        r"Cannot find module '([^']+)'|Error: Cannot find package",
        "A dependency is not installed in the environment you ran the command from.",
        "Check that your virtual environment is active (`which python` should point inside it).",
        "Install the project the way its CI does (the install command is listed below when you pass --repo).",
    ),
    _p(
        "runtime_version",
        r"requires a different Python|Requires-Python|python_requires|"
        r"Python \d+\.\d+ is not supported|The engine \"node\" is incompatible|Unsupported engine|"
        r"requires go >= ?\d|rustc [\d.]+ is not supported|edition20\d\d.*not stable|"
        r"SyntaxError: invalid syntax.*(?:match |:=)",
        "The project needs a different version of the language runtime than the one you have.",
        "Compare your version (`python --version`, `node --version`, `go version`, `rustc --version`) with the one CI uses.",
        "Install the matching version with a version manager such as pyenv, uv, nvm, or rustup instead of changing the project.",
    ),
    _p(
        "compiler_or_headers",
        r"Microsoft Visual C\+\+ \d+\.\d+ (?:or greater )?is required|error: linker `\w+` not found|"
        r"(?:gcc|g\+\+|clang|cc|cl\.exe)[^\n]{0,40}(?:not found|No such file)|"
        r"fatal error: [\w./-]+\.h: No such file|Failed building wheel for|node-gyp",
        "A package needs to compile native code and your machine lacks a compiler or C headers.",
        "Install build tools: Xcode command line tools on macOS (`xcode-select --install`), build-essential and the -dev headers on Debian or Ubuntu, Visual Studio Build Tools on Windows.",
        "Prefer a version of the package that ships prebuilt wheels, or use the project's dev container if it has one.",
    ),
    _p(
        "service_not_running",
        r"Connection refused|ECONNREFUSED|could not connect to server|Is the server running|"
        r"redis\.exceptions\.ConnectionError|Can't connect to (?:local )?MySQL",
        "The tests expect a service such as a database or cache, and nothing is listening.",
        "Start the service the tests need; CI's service containers are listed below when you pass --repo.",
        "Check the contributing guide for a docker compose file or a command that starts the services.",
    ),
    _p(
        "missing_env_var",
        r"KeyError: '([A-Z][A-Z0-9_]{2,})'|environment variable ([A-Z][A-Z0-9_]{2,}) (?:is )?not set|"
        r"Missing (?:required )?env(?:ironment)? var|\$\{?([A-Z][A-Z0-9_]{2,})\}? is (?:unset|empty)",
        "The code reads a setting from an environment variable that is not set in your shell.",
        "Look for a `.env.example` or the contributing guide's list of variables, and set the one named above.",
        "Never paste a real token into an issue or chat; use a dummy value if the tests only need one to exist.",
    ),
    _p(
        "command_not_found",
        r"command not found|is not recognized as an internal or external command|"
        r"No such file or directory: '(\w[\w.-]*)'$|executable file not found in \$PATH",
        "A tool the command calls is not installed, or not on your PATH.",
        "Install the tool named in the message, then open a new terminal so PATH is reloaded.",
        "If it is a project script, run it the way CI does (shown below when you pass --repo).",
    ),
    _p(
        "permission",
        r"Permission denied|EACCES|Operation not permitted",
        "The command tried to write somewhere your user cannot, often a system-wide install.",
        "Do not use sudo with pip or npm; install into a virtual environment or a user prefix instead.",
    ),
    _p(
        "network",
        r"ReadTimeoutError|Could not fetch URL|ETIMEDOUT|getaddrinfo ENOTFOUND|"
        r"Temporary failure in name resolution|SSL: CERTIFICATE_VERIFY_FAILED|Could not resolve host",
        "Downloading a dependency failed: the network, a proxy, or a certificate got in the way.",
        "Retry once; if it fails again, check a proxy or VPN, and try another network.",
    ),
    _p(
        "port_in_use",
        r"Address already in use|EADDRINUSE",
        "Something else is already listening on the port the command wants.",
        "Stop the other process (an earlier run of the same server is common), or set another port.",
    ),
    _p(
        "lockfile",
        r"lock ?file[^\n]{0,60}(?:out of (?:date|sync)|not (?:consistent|up to date))|"
        r"package-lock\.json[^\n]{0,40}(?:out of sync|not in sync)|`npm ci` can only install",
        "The lock file and the dependency list disagree, so a strict install refuses to continue.",
        "Use the install command from the contributing guide or CI rather than regenerating the lock file in your pull request.",
    ),
    _p(
        "out_of_memory",
        r"MemoryError|JavaScript heap out of memory|Killed$|signal 9",
        "The process ran out of memory.",
        "Run a smaller part of the test suite (one file or one test), or close other programs.",
    ),
    _p(
        "test_failure",
        r"^(?:FAILED|FAIL|--- FAIL:) |^E\s+AssertionError|\b\d+ failed\b|AssertionError",
        "Tests ran and some failed. That is not always your doing: some fail on the main branch too.",
        "Run the same test on a clean checkout of the main branch; if it fails there as well, it is not your change.",
        "If only your change fails it, read the assertion and the values it shows before editing code.",
    ),
)


def diagnose_output(text: str, *, ci: dict[str, Any] | None = None) -> dict[str, Any]:
    """Likely causes for a failed run, each with the line that matched.

    `ci` is optional: the `ci_environment` dictionary plus a `test_commands`
    list, used to add what CI sets up next to the causes that depend on it.
    """
    lines = (text or "").splitlines()
    causes: list[dict[str, Any]] = []
    for pattern in PATTERNS:
        for number, line in enumerate(lines, 1):
            match = pattern.regex.search(line)
            if not match:
                continue
            detail = next((g for g in match.groups() if g), None) if match.groups() else None
            cause: dict[str, Any] = {
                "id": pattern.id,
                "line": number,
                "quote": clean_untrusted(line.strip(), limit=200),
                "means": pattern.means,
                "try": list(pattern.try_),
            }
            if detail:
                cause["name"] = detail
            causes.append(cause)
            break

    # A test failure is usually a symptom when an environment cause is also present.
    if len(causes) > 1:
        causes = [c for c in causes if c["id"] != "test_failure"] or causes

    ci_notes: list[str] = []
    if ci:
        ids = {c["id"] for c in causes}
        runtimes = ci.get("runtimes") or []
        services = ci.get("services") or []
        commands = ci.get("test_commands") or []
        installs = ci.get("install_commands") or []
        if installs and ids & {
            "missing_module",
            "command_not_found",
            "lockfile",
            "compiler_or_headers",
        }:
            ci_notes += [f"CI installs with: {c['command']} ({c['source']})" for c in installs[:2]]
        if runtimes and ids & {"runtime_version", "missing_module", "compiler_or_headers"}:
            ci_notes += [
                f"CI uses {r['name']} {', '.join(r['versions'])} ({r['source']})" for r in runtimes
            ]
        if services and "service_not_running" in ids:
            names = ", ".join(
                f"{s['name']} ({s['image']})" if s.get("image") else s["name"] for s in services
            )
            ci_notes.append(f"CI starts these services for the tests: {names}")
        if commands and ids & {"missing_module", "command_not_found", "test_failure", "lockfile"}:
            ci_notes += [f"CI runs: {c['command']} ({c['source']})" for c in commands[:2]]
        if ci.get("runners"):
            ci_notes.append("CI runs on: " + ", ".join(ci["runners"]))

    if causes:
        summary = f"Most likely: {causes[0]['means']}"
    else:
        summary = (
            "No known failure shape matched. Ask in the project's channel with the last twenty "
            "lines of output, your operating system, and your runtime version "
            "(`git-into-gsoc draft question` gives the structure)."
        )
    return {"causes": causes, "ci": ci_notes, "summary": summary, "lines_read": len(lines)}
