"""Render the README's terminal demo from a real `git-into-gsoc start` run.

The command runs in a pseudo-terminal with scripted answers, against live public data
and a throwaway data folder, so the picture shows exactly what a newcomer sees today.
Run it again whenever the output changes:

    python scripts/demo.py               # writes brand/readme/demo-start.svg

It needs network access and a POSIX system (macOS, Linux, or WSL).
"""

from __future__ import annotations

import argparse
import io
import os
import pty
import re
import select
import shutil
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brand" / "readme" / "demo-start.svg"
WIDTH = 84

# Brand colours (brand/tokens.json): ink background, paper text, violet and lime accents.
THEME = TerminalTheme(
    (0x15, 0x12, 0x1E),
    (0xF4, 0xF1, 0xFA),
    [
        (0x15, 0x12, 0x1E),  # black
        (0xFF, 0x6A, 0x4D),  # red: danger
        (0xC6, 0xF4, 0x32),  # green: open (lime)
        (0xFF, 0xB2, 0x24),  # yellow: warn
        (0x7A, 0x5A, 0xF8),  # blue: merge
        (0xC2, 0xB5, 0xFF),  # magenta: merge-soft
        (0xC2, 0xB5, 0xFF),  # cyan: commands, merge-soft
        (0xF4, 0xF1, 0xFA),  # white: paper
    ],
    [
        (0x67, 0x60, 0x7A),
        (0xFF, 0x6A, 0x4D),
        (0xC6, 0xF4, 0x32),
        (0xFF, 0xB2, 0x24),
        (0x7A, 0x5A, 0xF8),
        (0xC2, 0xB5, 0xFF),
        (0xC2, 0xB5, 0xFF),
        (0xFF, 0xFF, 0xFF),
    ],
)

# A first-timer who skips the username, knows Python, likes science and data,
# has 8 hours a week, and shortlists the first match.
ANSWERS = ["", "python", "1, 4", "8", "1"]


def run(argv: list[str], answers: list[str], env: dict[str, str]) -> str:
    """Run a command in a pseudo-terminal, answering each `> ` prompt in turn."""
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.execvpe(argv[0], argv, env)
    output = b""
    pending = list(answers)
    while True:
        ready, _, _ = select.select([fd], [], [], 30)
        if not ready:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
        if output.rstrip(b" ").endswith(b">") and pending:
            time.sleep(0.2)
            os.write(fd, (pending.pop(0) + "\r").encode())
    os.waitpid(pid, 0)
    return output.decode("utf-8", errors="replace")


def tidy(raw: str) -> str:
    """Pseudo-terminals echo each answer with CRLF; keep plain newlines only."""
    text = raw.replace("\r\n", "\n").replace("\r", "")
    # The typed answer is echoed right after "> "; show an empty answer as "(Enter)".
    return re.sub(r"(  > )(?=\x1b\[0m\n|\n)", r"\1(Enter)", text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the README terminal demo.")
    parser.add_argument("--out", type=Path, default=OUT, help="SVG file to write")
    args = parser.parse_args()
    command = shutil.which("git-into-gsoc")
    if not command:
        print("Install the package first: pip install -e .", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as data:
        env = {
            **os.environ,
            "COLUMNS": str(WIDTH),
            "LINES": "200",
            "TERM": "xterm-256color",
            "GIG_DATA_DIR": data,
            "GIG_USE_GH_CLI": "false",  # show what someone without a token sees
        }
        for key in ("GITHUB_TOKEN", "GH_TOKEN", "GIG_GITHUB_TOKEN", "NO_COLOR"):
            env.pop(key, None)
        raw = run([command, "start"], ANSWERS, env)
    console = Console(
        record=True,
        width=WIDTH,
        force_terminal=True,
        color_system="truecolor",
        file=io.StringIO(),  # recorded for the SVG only
    )
    console.print(Text.from_markup("[bold #C6F432]$[/] git-into-gsoc start"))
    console.print(Text.from_ansi(tidy(raw)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(args.out), title="git-into-gsoc start", theme=THEME)
    print(f"wrote {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
