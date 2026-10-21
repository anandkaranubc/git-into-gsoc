"""Run beginner journeys against live GitHub, GitLab, and GSoC data, the way people do.

Unit tests block the network, so they cannot show that a command still works on
real pages, real issues, and a real Windows console. This runs the installed
command once per step in a temporary progress folder and reports each step:

- PASS: it ran and the answer contains what the journey expects.
- DRIFT: it ran, but the answer changed. Live data moves (an issue gets a pull
  request, an org updates its wiki), so this is a note to look at, not a failure.
- CRASH: a traceback, a timeout, or an exit status other than 0 or 1 (1 is a
  handled error with a hint). Any crash makes the run fail.

Usage:
    python scripts/live_journeys.py [--command "python -m git_into_gsoc"] [--summary FILE]

Set GITHUB_TOKEN for the full GitHub rate limit; without it each search uses part
of the 60 requests an hour GitHub allows.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEAK_PROPOSAL = ROOT / "tests" / "fixtures" / "proposal_weak.md"
FAILED_SETUP = "npm error `npm ci` can only install packages when your package.json and "
FAILED_SETUP += "package-lock.json are in sync.\n"

# (name, arguments, text the answer should contain)
JOURNEYS: list[tuple[str, list[str], str]] = [
    ("program timeline", ["program", "--year", "2027"], "GSoC 2027"),
    ("organizations for Python", ["orgs", "--tech", "python", "-n", "3"], "Projects"),
    ("one organization", ["org", "SymPy"], "SymPy"),
    ("ideas page", ["ideas", "GNOME Foundation", "-n", "3"], "Ideas"),
    ("repositories of an org", ["repos", "SymPy", "-n", "3"], "sympy"),
    ("repository grade", ["repo", "sympy/sympy"], "grade"),
    ("beginner issues", ["issues", "--language", "python", "-n", "3"], "issue"),
    ("issue status on GitHub", ["issue", "sympy/sympy#3100"], "Status: closed"),
    (
        "issue status on GitLab",
        ["issue", "https://gitlab.gnome.org/GNOME/gitg/-/issues/494"],
        "Status:",
    ),
    ("org whose code is on GitLab", ["issues", "--org", "GNOME Foundation"], "outside GitHub"),
    ("read-only mirror", ["repo", "GNOME/gitg"], "Not graded"),
    ("orient in a repository", ["orient", "sympy/sympy"], "Read in this order"),
    ("intro draft", ["draft", "intro", "--org", "SymPy"], "In "),
    ("proposal check", ["proposal", "check", str(WEAK_PROPOSAL), "--no-verify"], "Not ready"),
    ("diagnose a failed setup", ["diagnose", "-"], "lock file"),
    ("doctor", ["doctor"], "GitHub"),
]


def run(
    command: list[str], args: list[str], env: dict[str, str], stdin: str | None
) -> tuple[str, str]:
    """(verdict, output) for one step."""
    try:
        done = subprocess.run(
            [*command, *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return "CRASH", "timed out after 300 seconds"
    output = (done.stdout or "") + (done.stderr or "")
    if "Traceback (most recent call last)" in output or done.returncode not in (0, 1):
        return "CRASH", output
    return "OK", output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run beginner journeys against live data.")
    parser.add_argument(
        "--command", help="How to start the tool (default: this Python with -m git_into_gsoc)"
    )
    parser.add_argument("--summary", help="Append a Markdown table to this file")
    options = parser.parse_args()
    # A list, not a string: on Windows a quoted interpreter path does not split back.
    command = (
        shlex.split(options.command, posix=os.name != "nt")
        if options.command
        else [sys.executable, "-m", "git_into_gsoc"]
    )
    rows: list[tuple[str, str, float, str]] = []
    with tempfile.TemporaryDirectory() as home:
        env = {
            **os.environ,
            "GIG_DATA_DIR": str(Path(home) / "data"),
            "GIG_CACHE_DIR": str(Path(home) / "cache"),
            "COLUMNS": "120",
        }
        for name, args, expected in JOURNEYS:
            start = time.monotonic()
            stdin = FAILED_SETUP if args == ["diagnose", "-"] else None
            verdict, output = run(command, args, env, stdin)
            if verdict == "OK":
                verdict = "PASS" if expected.lower() in output.lower() else "DRIFT"
            seconds = time.monotonic() - start
            first = next((line.strip() for line in output.splitlines() if line.strip()), "")
            rows.append((name, verdict, seconds, first[:100]))
            print(f"{verdict:<6} {seconds:5.1f}s  {name}")
            if verdict != "PASS":
                print("       " + "\n       ".join(output.strip().splitlines()[-12:]))
    crashes = sum(1 for row in rows if row[1] == "CRASH")
    drift = sum(1 for row in rows if row[1] == "DRIFT")
    print(f"\n{len(rows) - crashes - drift} passed, {drift} drifted, {crashes} crashed")
    if options.summary:
        with open(options.summary, "a", encoding="utf-8") as summary:
            summary.write(f"### Live journeys on {sys.platform}\n\n| Step | Result | Seconds |\n")
            summary.write("|---|---|---|\n")
            for name, verdict, seconds, _ in rows:
                summary.write(f"| {name} | {verdict} | {seconds:.1f} |\n")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main())
