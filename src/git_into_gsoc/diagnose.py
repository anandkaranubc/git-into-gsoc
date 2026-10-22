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
        # NumPy's CI (2026-10-22): a test imported a name its built copy did not have yet,
        # and the advice was to install a missing dependency.
        "import_mismatch",
        r"cannot import name '(\w+)' from (?:partially initialized module )?'[\w.]+'|"
        r"does not provide an export named '(\w+)'|export '(\w+)' \(imported as '\w+'\) was not found",
        "A module was found, but it lacks a name the code imports. Usually the installed copy "
        "is older or newer than the code: a dependency at another version, or the project's "
        "own build left behind after you pulled new changes.",
        "If the module belongs to the project, reinstall or rebuild it the way CI does, so the "
        "installed copy matches the code.",
        "If it is a dependency, compare its version (`pip show NAME` or `npm ls NAME`) with the "
        "version the project asks for, and install that one.",
        "If the line says 'circular import', two modules import each other: look at the "
        "imports your change added.",
    ),
    _p(
        "missing_module",
        r"ModuleNotFoundError: No module named '([\w.]+)'|"
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
        r"Permission denied|\bEACCES\b|Operation not permitted",
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
        "Use the install command from the README, contributing guide, or CI. If the strict "
        "install still refuses, the plain one (such as npm install) updates the lock file on "
        "your machine: keep that change out of your pull request (git checkout -- "
        "package-lock.json before you commit) and tell the maintainers the lock file is stale.",
    ),
    _p(
        "out_of_memory",
        r"MemoryError|JavaScript heap out of memory|Killed$|signal 9",
        "The process ran out of memory.",
        "Run a smaller part of the test suite (one file or one test), or close other programs.",
    ),
    _p(
        # A first pull request often fails here, not in the tests. SymPy's code-quality
        # test failed a newcomer's branch (2026-10-22) on "File contains trailing
        # whitespace: ..., line 445", and the only advice was that tests failed.
        "style_check",
        r"trailing whitespace:|\bW29[123]\b|\(trailing-whitespace\)|no-trailing-spaces|"
        r":\d+:\d+: [A-Z]{1,4}\d{3,4}\b|line too long \(\d+|would reformat|"
        r"files? would be reformatted|incorrectly sorted|\d+ problems? \(\d+ errors?|"
        r"\d+ offenses? detected|Code style issues found|format violations|"
        r"clang-format-violations|File is not (?:properly formatted|\S*-ed\b)|"
        r"Diff in \S+(?: at line |:)\d+|fixable with the .?--fix.? option|"
        # A failed pre-commit or prek hook, unless the hook runs tests or a type checker.
        r"^(?!.*\b(?:tests?|pytest|unittest|jest|vitest|mypy|pyright|type[ _-]?check\w*)\b)"
        r".*\.{3,}\s*Failed$",
        "A style check failed. Your code may work, but its layout breaks one of the "
        "project's rules, such as spaces at the end of a line, line length, or the order of "
        "imports.",
        "Run the formatter or linter the project uses and commit what it changes. The "
        "contributing guide or the CI file names it: often pre-commit, ruff, black, flake8, "
        "eslint, or prettier.",
        "For trailing whitespace (spaces at the end of a line), delete them on the line "
        "named above. Most editors can show them or remove them when you save.",
    ),
    _p(
        "test_failure",
        r"^(?:FAILED|FAIL|--- FAIL:) |^(?:FAIL|ERROR): test\w* \(|^E\s+AssertionError|"
        r"\b[1-9]\d* failed\b|AssertionError",
        "Tests ran and some failed. That is not always your doing: some fail on the main branch too.",
        "Run the same test on a clean checkout of the main branch; if it fails there as well, it is not your change.",
        "If only your change fails it, read the assertion and the values it shows before editing code.",
    ),
)


# `gh run view --log` starts each line with the job, the step, and a timestamp, and a
# log downloaded from the Actions page starts it with the timestamp. Colour codes come
# through too, and gh writes their escape character as the two characters "^[".
# Without them the quote keeps the detail that matters, and patterns anchored at the
# line start match.
_CI_PREFIX = re.compile(r"^\ufeff?(?:[^\t]*\t[^\t]*\t)?\d{4}-\d\d-\d\dT[\d:.]+Z ?")
_COLOUR = re.compile(r"(?:\x1b|\^\[)\[[\d;]*[A-Za-z]")
# A test that passed, or failed as expected, is not evidence, even when its name says
# "permission denied". unittest ends such lines with "... ok", pytest prints PASSED.
# Nor is a build tool trying one tool after another: Meson prints "Detecting archiver
# via: `llvm-ar-20 --version` -> [Errno 2] No such file or directory" and then finds ar.
_NOT_EVIDENCE = re.compile(
    r" \.\.\. (?:ok|skipped\b.*|expected failure)$|\b(?:PASSED|XFAIL|XPASS)\b|"
    r"^Detecting [\w ]+ via: "
)
_NAMED_TEST = re.compile(r"^(?:FAILED|FAIL|--- FAIL:) |^(?:FAIL|ERROR): test\w* \(")
_STYLE = next(p for p in PATTERNS if p.id == "style_check")


def _evidence(pattern: Pattern, lines: list[str]) -> tuple[int, str, re.Match[str]] | None:
    """The first line that matches, or for failing tests the line that names one."""
    hits = (
        (n, line, m)
        for n, line in enumerate(lines, 1)
        if (m := pattern.regex.search(line)) and not _NOT_EVIDENCE.search(line)
    )
    if pattern.id != "test_failure":
        return next(hits, None)
    # A style check can run as a test, as SymPy's does. style_check reports that one, so
    # a test failure is only reported for another test.
    others = [hit for hit in hits if not _STYLE.regex.search(hit[1])]
    named = [hit for hit in others if _NAMED_TEST.search(hit[1])]
    if not named and any(_NAMED_TEST.search(line) for line in lines):
        return None
    return named[0] if named else (others[0] if others else None)


_STEP_START = re.compile(r"^##\[group\]Run (.+)$")
_PROCESS_FAILED = re.compile(r"^##\[error\]Process completed with exit code \d+")
# Red text: projects print their own explanation of a failed check in red (SymPy's
# "This author is not included in the .mailmap file:").
_RED_ON = re.compile(r"(?:\x1b|\^\[)\[(?:\d+;)*(?:31|91)(?:;\d+)*m")
_RESET = re.compile(r"(?:\x1b|\^\[)\[0?m")
_ERRORISH = re.compile(
    r"\berror\b|\bfail|\bnot\b|\bmust\b|\bmissing\b|\bplease\b|\brequired?\b|\bsee:?$|https?://",
    re.I,
)
# Logs list other people's names and addresses (SymPy's prints every new author).
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Passing tests and progress dots are not what went wrong (Django's "... ok",
# Vitest's "✓ matches expected screenshots", pytest's ".....F.. [ 93%]").
_PROGRESS = re.compile(r"^[.sFExX]+\s*\[\s*\d+%\]$|^\s*[✓√]\s")


def failing_step(text: str, *, limit: int = 6) -> dict[str, Any] | None:
    """What the failing step of a GitHub Actions log printed, or None for other output.

    The step is the last "Run ..." group before "Process completed with exit code".
    Its red lines and error annotations come first, then lines that read like an
    error, then the rest. Quoted lines are cleaned, and email addresses are hidden.
    """
    raw = [_CI_PREFIX.sub("", line, count=1) for line in (text or "").splitlines()]
    end = next((n for n, line in enumerate(raw) if _PROCESS_FAILED.match(line)), None)
    if end is None:
        return None
    start = next((n for n in range(end - 1, -1, -1) if _STEP_START.match(raw[n])), None)
    if start is None:
        return None
    step = _STEP_START.match(raw[start])
    command = _COLOUR.sub("", step.group(1) if step else "").strip()
    body = next((n + 1 for n in range(start, end) if raw[n].startswith("##[endgroup]")), start + 1)
    red: list[str] = []
    rest: list[str] = []
    in_red = False
    for line in raw[body:end]:
        annotation = line.startswith("##[error]")
        if line.startswith("##[") and not annotation:
            continue
        in_red = in_red or bool(_RED_ON.search(line))
        shown = _COLOUR.sub("", line.removeprefix("##[error]")).strip()
        if shown and not _NOT_EVIDENCE.search(shown) and not _PROGRESS.search(shown):
            (red if in_red or annotation else rest).append(shown)
        last_red = max((m.end() for m in _RED_ON.finditer(line)), default=-1)
        if max((m.end() for m in _RESET.finditer(line)), default=-1) > last_red:
            in_red = False
    # Without red text, a failure's summary is at the end of the step.
    tail = rest[-60:]
    errorish = [shown for shown in tail if _ERRORISH.search(shown)][-limit:]
    printed: list[str] = []
    for shown in red or errorish or tail[-limit:]:
        quote = clean_untrusted(_EMAIL.sub("<email>", shown), limit=200)
        if quote and quote not in printed:
            printed.append(quote)
        if len(printed) >= limit:
            break
    if not printed:
        return None
    return {"command": clean_untrusted(command, limit=120), "printed": printed}


def diagnose_output(text: str, *, ci: dict[str, Any] | None = None) -> dict[str, Any]:
    """Likely causes for a failed run, each with the line that matched.

    `ci` is optional: the `ci_environment` dictionary plus a `test_commands`
    list, used to add what CI sets up next to the causes that depend on it.
    """
    lines = [
        _COLOUR.sub("", _CI_PREFIX.sub("", line, count=1)) for line in (text or "").splitlines()
    ]
    causes: list[dict[str, Any]] = []
    for pattern in PATTERNS:
        found = _evidence(pattern, lines)
        if not found:
            continue
        number, line, match = found
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

    # A test failure is usually a symptom when an environment cause is also present. A
    # style failure is no such cause: a real failing test next to it still counts.
    if any(c["id"] not in {"test_failure", "style_check"} for c in causes):
        causes = [c for c in causes if c["id"] != "test_failure"]

    ci_notes: list[str] = []
    if ci:
        ids = {c["id"] for c in causes}
        runtimes = ci.get("runtimes") or []
        services = ci.get("services") or []
        commands = ci.get("test_commands") or []
        installs = ci.get("install_commands") or []
        if installs and ids & {
            "import_mismatch",
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
        if commands and ids & {
            "missing_module",
            "command_not_found",
            "test_failure",
            "style_check",
            "lockfile",
        }:
            ci_notes += [f"CI runs: {c['command']} ({c['source']})" for c in commands[:2]]
        if ci.get("runners"):
            ci_notes.append("CI runs on: " + ", ".join(ci["runners"]))

    step = failing_step(text)
    if causes:
        summary = f"Most likely: {causes[0]['means']}"
    elif step:
        # A project's own check usually says what is wrong and links its instructions.
        summary = (
            f"No known failure shape matched, but the failing step (`{step['command']}`) "
            "printed its own explanation, quoted below. Read it first, then follow any link "
            "it gives."
        )
    else:
        summary = (
            "No known failure shape matched. Ask in the project's channel with the last twenty "
            "lines of output, your operating system, and your runtime version "
            "(`git-into-gsoc draft question` gives the structure)."
        )
    result = {"causes": causes, "ci": ci_notes, "summary": summary, "lines_read": len(lines)}
    if step:
        result["step"] = step
    return result
