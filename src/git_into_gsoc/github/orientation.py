"""Repository orientation for a first contribution: facts and paths, no prose.

Everything here is a pure function over GitHub API payloads (the recursive
tree, commits, workflow files, CONTRIBUTING and PR template text). The output
names files a newcomer should open, the real test command from CI, who merges,
and the rules that apply before a PR (sign-off, CLA, commit style), each with
the path or URL that proves it. Purpose guesses are labelled as guesses.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.text import clean_untrusted

PURPOSES: dict[str, tuple[str, ...]] = {
    "source": ("src", "lib", "pkg", "internal", "core", "app", "cmd", "packages", "crates"),
    "tests": (
        "tests",
        "test",
        "spec",
        "specs",
        "__tests__",
        "e2e",
        "testing",
        "autotest",
        "unittest",
        "unittests",
    ),
    "docs": ("docs", "doc", "site", "website", "documentation", "wiki", "man"),
    "examples": ("examples", "example", "samples", "galleries", "demo", "demos", "tutorials"),
    "tooling": ("scripts", "tools", "bin", "ci", ".github", ".circleci", "build", "dev"),
    "vendored": ("extern", "vendor", "third_party", "thirdparty", "node_modules", "external"),
    "perf": ("benchmarks", "benchmark", "bench", "perf"),
    "data": ("data", "assets", "resources", "fixtures", "static"),
}
_PURPOSE_BY_NAME = {name: purpose for purpose, names in PURPOSES.items() for name in names}

ARCH_DOC_RE = re.compile(
    r"^(?:docs?/(?:dev(?:elop(?:er|ment))?/|contributing/|internals?/|design/)?)?"
    r"(?:ARCHITECTURE|HACKING|DEVELOPING|DEVELOPMENT|DESIGN|INTERNALS|CONTRIBUTING)"
    r"[^/]*\.(?:md|rst|txt|adoc)$",
    re.I,
)
# A project's own test script, when it is the command being run: Zulip runs
# ./tools/test-backend, SymPy bin/test; `cp scripts/test-data/x .` runs no tests.
_TEST_SCRIPT = (
    r"(?:^|[;&|]\s*|\b(?:bash|sh|python3?|node)\s+)\.?/?(?:tools|scripts|bin)/"
    # Each part after a dash or underscore is letters and digits only, so a name splits
    # one way (CodeQL flagged `[-_]\w+` repeated as exponential backtracking).
    r"(?:run[-_])?tests?(?:[-_][^\W_]+)*(?:\.\w+)?(?=\s|$)"
)
TEST_RUNNER_RE = re.compile(
    r"\b(pytest|python -m pytest|tox\b|nox\b|npm (?:run )?test\w*|pnpm (?:run )?test\w*|yarn test\w*|"
    r"cargo test|go test|make (?:test|check)|mvn (?:test|verify)|gradle(?:w)? test|ctest|"
    r"meson test|bundle exec rspec|rspec|phpunit|dotnet test|swift test|mix test|"
    r"ninja test|hatch test|poetry run pytest|uv run pytest|just test|"
    r"python -m unittest|autotest\.py|\w+_unittest\.py)\b|" + _TEST_SCRIPT,
    re.I,
)
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|chore|refactor|test|tests|ci|build|perf|style|revert|deps)(\([^)]*\))?!?:\s",
    re.I,
)
COMMITLINT_FILES = (
    ".commitlintrc",
    ".commitlintrc.json",
    ".commitlintrc.yaml",
    ".commitlintrc.yml",
    ".commitlintrc.js",
    ".commitlintrc.cjs",
    ".commitlintrc.mjs",
    ".commitlintrc.ts",
    "commitlint.config.js",
    "commitlint.config.cjs",
    "commitlint.config.mjs",
    "commitlint.config.ts",
    ".cz.toml",
    ".cz.json",
    "release-please-config.json",
    ".releaserc",
    ".releaserc.json",
    "cliff.toml",
)
ENTRY_FILE_RE = re.compile(
    r"(?:^|/)(?:__main__\.py|main\.py|cli\.py|app\.py|server\.py|manage\.py|main\.go|main\.rs|"
    r"Main\.java|index\.(?:js|ts)|main\.(?:js|ts|c|cpp|cc))$"
)
KNOWN_BOTS = {"dependabot", "renovate", "pre-commit-ci", "github-actions", "allcontributors"}

POLICY_PATTERNS: dict[str, re.Pattern[str]] = {
    "assignment": re.compile(
        r"\b(do not assign|don't assign|we don't assign|not assign issues|assign(?:ed|ment)? "
        r"(?:policy|process)|claim(?:ing)? (?:an |the )?issue|/assign\b|\.take\b|self-assign)",
        re.I,
    ),
    "ai": re.compile(
        r"\b(ai[- ]generated|ai[- ]assist\w*|ai disclosure|generative ai|llm|chatgpt|copilot|"
        r"no ai\b|ai tools?)\b",
        re.I,
    ),
    "pr_limit": re.compile(
        r"\b(one (?:pull request|pr) at a time|one open (?:pull request|pr)|"
        r"finish (?:your|one) (?:pull request|pr)|limit(?:ed)? to one)\b",
        re.I,
    ),
    "first_timer": re.compile(
        r"\b(first[- ]time contributors?|newcomers?|new contributors?|good first issue)\b", re.I
    ),
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _paths(tree: list[dict[str, Any]], kind: str = "blob") -> list[str]:
    return [str(e.get("path")) for e in tree if e.get("type") == kind and e.get("path")]


def code_map(
    tree: list[dict[str, Any]], *, limit: int = 12, repo_name: str | None = None
) -> list[dict[str, Any]]:
    """Top-level directories with file counts, dominant extension, and a purpose guess."""
    files_by_dir: Counter[str] = Counter()
    ext_by_dir: dict[str, Counter[str]] = {}
    root_files = 0
    for path in _paths(tree):
        if "/" not in path:
            root_files += 1
            continue
        top = path.split("/", 1)[0]
        files_by_dir[top] += 1
        ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
        ext_by_dir.setdefault(top, Counter())[f".{ext}" if ext else "(none)"] += 1
    rows = []
    for top, count in files_by_dir.most_common(limit):
        purpose = _PURPOSE_BY_NAME.get(top.lower())
        main_ext = ext_by_dir[top].most_common(1)[0][0] if ext_by_dir.get(top) else ""
        if (
            purpose is None
            and repo_name
            and top.lower().replace("-", "_") == repo_name.lower().replace("-", "_")
        ):
            purpose = "source (main package)"
        elif purpose is None and main_ext in {".md", ".rst", ".txt"}:
            purpose = "docs"
        rows.append(
            {
                "path": top,
                "files": count,
                "main_extension": main_ext,
                "purpose": purpose or "unknown",
                "purpose_is_guess": True,
            }
        )
    if root_files:
        rows.append(
            {
                "path": ".",
                "files": root_files,
                "main_extension": "",
                "purpose": "project root",
                "purpose_is_guess": False,
            }
        )
    return rows


_FRAGMENT_DIRS = (
    "changelog.d",
    ".changeset",
    "newsfragments",
    "upcoming_changes",
    "next_whats_new",
)
_GENERIC_FRAGMENT_DIRS = ("changelog", "changes", "news")
_FRAGMENT_FILE_RE = re.compile(
    r"^(?:\d+|\+[\w-]+)\.[a-z]+(?:\.(?:rst|md|txt))?$"
    r"|\.(?:feature|bugfix|bug|doc|docs|removal|misc|trivial|improvement|breaking|deprecation)\.(?:rst|md|txt)$",
    re.I,
)


def _news_fragment_dir(trees: list[str], blobs: list[str]) -> str | None:
    """The directory where each change gets its own news entry, if the repository has one.

    Specific names count on their own. A generic `changelog`, `changes` or `news`
    directory counts only when it holds fragment-shaped files such as
    `1234.bugfix.rst`; otherwise it is usually a folder of full release notes.
    """
    for name in _FRAGMENT_DIRS:
        for tree in sorted(trees, key=lambda t: t.count("/")):
            if tree.rsplit("/", 1)[-1].lower() == name:
                return tree
    for tree in sorted(trees, key=lambda t: t.count("/")):
        if tree.rsplit("/", 1)[-1].lower() in _GENERIC_FRAGMENT_DIRS:
            children = [b.rsplit("/", 1)[-1] for b in blobs if b.startswith(tree + "/")]
            if sum(1 for c in children if _FRAGMENT_FILE_RE.search(c)) >= 2:
                return tree
    return None


def find_paths(tree: list[dict[str, Any]]) -> dict[str, Any]:
    """Paths that matter to a newcomer, found in the tree (never guessed)."""
    blobs = _paths(tree)
    trees = _paths(tree, "tree")
    lower = {p.lower(): p for p in blobs}

    def first(*names: str) -> str | None:
        for name in names:
            if name.lower() in lower:
                return lower[name.lower()]
        return None

    # A CONTRIBUTING file anywhere is the contributing guide, not an architecture doc:
    # MDAnalysis's docs/CONTRIBUTING.rst was listed as both.
    arch = [
        p
        for p in blobs
        if ARCH_DOC_RE.match(p) and not p.rsplit("/", 1)[-1].upper().startswith("CONTRIBUTING")
    ]
    workflows = [
        p for p in blobs if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
    ]
    test_file_re = re.compile(
        r"(?:^|/)(?:test_[^/]+|[^/]+_test\.[a-z]+|[^/]+\.test\.[a-z]+|[^/]+\.spec\.[a-z]+|[^/]+Test\.java)$"
    )
    candidates = [t for t in trees if t.rsplit("/", 1)[-1].lower() in PURPOSES["tests"]]
    weight = {
        t: sum(1 for p in blobs if p.startswith(t + "/") and test_file_re.search(p))
        for t in candidates
    }
    test_dirs = sorted(candidates, key=lambda t: (-weight[t], t.count("/"), t))
    return {
        "readme": first("README.md", "README.rst", "README.txt", "README", "readme.md"),
        "contributing": first(
            "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md", "CONTRIBUTING.rst"
        ),
        "architecture_docs": sorted(arch)[:5],
        "codeowners": first("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"),
        "pr_template": first(
            ".github/PULL_REQUEST_TEMPLATE.md",
            "PULL_REQUEST_TEMPLATE.md",
            "docs/PULL_REQUEST_TEMPLATE.md",
            ".github/pull_request_template.md",
        ),
        # Names only, so keep them all: ArduPilot has 33, and an alphabetical cut at 20
        # dropped test_unit_tests.yml before the ranking could see it.
        "workflows": sorted(workflows)[:100],
        "test_dirs": test_dirs[:8],
        "pre_commit": ".pre-commit-config.yaml" in lower,
        "commitlint": any(name.lower() in lower for name in COMMITLINT_FILES),
        "dco_file": first(".github/dco.yml", "DCO", "DCO.md", "DCO.txt"),
        "cla_file": first("CLA.md", "CLA", ".clabot", "CONTRIBUTOR_LICENSE_AGREEMENT.md"),
        "devcontainer": any(p.startswith(".devcontainer") for p in blobs),
        "news_fragments": _news_fragment_dir(trees, blobs),
        "pyproject": first("pyproject.toml"),
        "package_json": first("package.json"),
        "makefile": first("Makefile", "justfile", "Justfile", "noxfile.py", "tox.ini"),
        "governance": first(
            "GOVERNANCE.md", "MAINTAINERS.md", "MAINTAINERS", "CONTRIBUTOR_LADDER.md"
        ),
    }


def entry_points(
    tree: list[dict[str, Any]],
    *,
    pyproject: str | None = None,
    package_json: str | None = None,
    limit: int = 6,
) -> list[dict[str, str]]:
    """Likely entry points: manifests first, then conventional file names (shallowest first)."""
    points: list[dict[str, str]] = []
    blobs = set(_paths(tree))
    if pyproject:
        section = re.search(r"\[project\.scripts\]\s*\n((?:[^\[\n][^\n]*\n?)*)", pyproject)
        if section:
            for line in section.group(1).splitlines():
                match = re.match(r'\s*([\w.-]+)\s*=\s*"([^"]+)"', line)
                if match:
                    module = match.group(2).split(":")[0].replace(".", "/")
                    # The module's real file, under src/, lib/ or wherever it is: the
                    # guess "mdacli/__main__.py" did not exist. Not in the tree: dropped.
                    ends = (f"{module}.py", f"{module}/__init__.py")
                    found_at = sorted(
                        (b for b in blobs if b in ends or b.endswith(tuple("/" + e for e in ends))),
                        key=lambda b: (b.count("/"), b),
                    )
                    path = found_at[0] if found_at else None
                    if path:
                        points.append(
                            {
                                "path": path,
                                "reason": f"pyproject.toml [project.scripts] {match.group(1)} = {match.group(2)}",
                            }
                        )
    if package_json:
        for key in ("main", "bin"):
            match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', package_json)
            if match:
                points.append({"path": match.group(1), "reason": f'package.json "{key}"'})
    candidates = sorted(
        (p for p in _paths(tree) if ENTRY_FILE_RE.search(p)),
        key=lambda p: (p.count("/"), len(p)),
    )
    for path in candidates:
        if any(path == x["path"] for x in points):
            continue
        name = path.rsplit("/", 1)[-1]
        reason = {
            "__main__.py": "module entry point (python -m)",
            "main.go": "Go main package",
            "main.rs": "Rust binary",
            "Main.java": "Java main class",
        }.get(name, "conventional entry file name")
        points.append({"path": path, "reason": reason})
    return points[:limit]


def ci_test_commands(workflows: dict[str, str], *, limit: int = 4) -> list[dict[str, str]]:
    """Commands CI really runs for tests, read from `run:` steps of workflow files."""
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for path, text in workflows.items():
        for block in _run_blocks(text):
            for command in _commands(block):
                if not command or command.startswith("#"):
                    continue
                # "pip install pytest-xdist" installs a test runner; it runs nothing.
                if _INSTALL_RE.search(command):
                    continue
                if TEST_RUNNER_RE.search(command) and command not in seen:
                    seen.add(command)
                    found.append({"command": _shorten(command), "source": path})
    # A project's own script (SymPy's bin/test quality runs only the code-quality tests)
    # comes after a standard runner; Zulip has only scripts, so they are what it lists.
    found.sort(key=lambda c: bool(_TEST_SCRIPT_RE.search(c["command"])))
    return found[:limit]


_TEST_SCRIPT_RE = re.compile(_TEST_SCRIPT, re.I)


def _commands(block: str) -> list[str]:
    """The commands in a `run:` block, with lines continued by a backslash joined.

    MDAnalysis spreads one `pip install` over a dozen lines; read line by line, a draft
    said to run `python -m pip install` with nothing to install.
    """
    out: list[str] = []
    current = ""
    for line in block.splitlines():
        part = line.strip()
        if part.endswith("\\"):
            current += part[:-1].strip() + " "
            continue
        out.append(_COMMENT_RE.sub("", current + part).strip())
        current = ""
    if current:
        out.append(_COMMENT_RE.sub("", current).strip())
    return out


# A shell comment ends the command, also after a continued line ("pkg \ # Base deps").
_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")


def _shorten(command: str, limit: int = 160) -> str:
    """A long command cut at a word, ending in "..." so it never looks complete."""
    if len(command) <= limit:
        return command
    return command[: limit - 4].rsplit(" ", 1)[0] + " ..."


_RUNTIME_KEYS = {
    "python-version": "Python",
    "node-version": "Node.js",
    "go-version": "Go",
    "java-version": "Java",
    "ruby-version": "Ruby",
    "dotnet-version": "the .NET SDK",
    "php-version": "PHP",
    "toolchain": "Rust",
}
_KEY_LINE_RE = re.compile(r"^(\s*)(?:-\s+)?([A-Za-z][\w-]*):\s*(.*?)\s*(?:#.*)?$")


_RUST_TOOLCHAIN_RE = re.compile(r"^(?:stable|beta|nightly|\d+\.\d+(?:\.\d+)?)(?:-|$)")


def _scalar_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and not value.endswith("]"):
        return []  # a flow list continued on later lines; not worth guessing at
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    items = [v.strip().strip("'\"") for v in value.split(",")] if value else []
    return [v for v in items if v and "${{" not in v]


def _block_list(lines: list[str], start: int, indent: int) -> list[str]:
    """`key:` followed by `- item` lines indented deeper."""
    items: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        stripped = line.strip()
        if depth <= indent or not stripped.startswith("- "):
            break
        items.append(stripped[2:].strip().strip("'\""))
    return items


def ci_environment(workflows: dict[str, str]) -> dict[str, Any]:
    """What CI actually sets up: runtime versions (matrix values included),
    service containers, and runner operating systems. Setup instructions in a
    README drift; the workflow is what runs."""
    runtimes: dict[str, set[str]] = {}
    uses: dict[str, Counter[str]] = {}  # how many jobs name each version
    sources: dict[str, str] = {}
    services: list[dict[str, str]] = []
    runners: set[str] = set()
    for path, text in workflows.items():
        lines = text.splitlines()
        matrix: dict[str, list[str]] = {}
        for index, line in enumerate(lines):
            match = _KEY_LINE_RE.match(line)
            if not match:
                continue
            indent, key, value = len(match.group(1)), match.group(2), match.group(3)
            values = _scalar_list(value) if value else _block_list(lines, index, indent)
            if key in _RUNTIME_KEYS or key.endswith("-version"):
                matrix.setdefault(key, [])
                matrix[key].extend(v for v in values if v not in matrix[key])
                runtime = _RUNTIME_KEYS.get(key)
                if runtime:
                    uses.setdefault(runtime, Counter()).update(values)
            elif key == "runs-on" and value and "${{" not in value:
                runners.update(_scalar_list(value))
            elif key == "os" and values:
                runners.update(values)
            elif key == "services" and not value:
                for child in lines[index + 1 :]:
                    if not child.strip():
                        continue
                    depth = len(child) - len(child.lstrip())
                    if depth <= indent:
                        break
                    sub = _KEY_LINE_RE.match(child)
                    if sub and len(sub.group(1)) == indent + 2 and not sub.group(3):
                        services.append({"name": sub.group(2), "image": "", "source": path})
                    elif sub and sub.group(2) == "image" and services and not services[-1]["image"]:
                        services[-1]["image"] = sub.group(3).strip("'\"")
        for key, values in matrix.items():
            name = _RUNTIME_KEYS.get(key)
            if key == "toolchain":
                # A matrix "toolchain" is often a build target (ArduPilot: chibios);
                # it means Rust only when the values are Rust channels or versions.
                values = [v for v in values if _RUST_TOOLCHAIN_RE.match(v)]
            if not name or not values:
                continue
            runtimes.setdefault(name, set()).update(values)
            sources.setdefault(name, path)

    def version_key(v: str) -> tuple[bool, tuple[int, ...], str]:
        # Plain versions first, numerically; other implementations (pypy2.7) after.
        return (not v[:1].isdigit(), tuple(int(p) for p in re.findall(r"\d+", v)), v)

    def most_used(name: str) -> str | None:
        counts = uses.get(name)
        if not counts:
            return None
        (top, n), *rest = [*counts.most_common(2), ("", 0)]
        return top if n > 1 and n > rest[0][1] else None

    return {
        "runtimes": [
            {
                "name": name,
                "versions": sorted(values, key=version_key)[:8],
                "most_used": most_used(name),
                "source": sources[name],
            }
            for name, values in sorted(runtimes.items())
        ],
        "services": [s for s in services if s["name"] not in {"image", "env", "ports", "options"}][
            :6
        ],
        "runners": sorted(runners)[:4],
    }


_INSTALL_RE = re.compile(
    r"\b(?:pip3? install|python -m pip install|uv (?:sync|pip install)|poetry install|"
    r"pdm install|hatch env create|conda env create|npm (?:ci|clean-install|install)|"
    # Bare "yarn" installs; "yarn test:e2e" or "yarn build" runs a script.
    r"yarn(?: install)?(?=\s*$|\s+-|\s*[;&|])|"
    r"pnpm install|bundle install|go mod download|cargo (?:build|fetch))",
    re.I,
)


# "pip install --upgrade pip setuptools" prepares the installer; it installs nothing of the project.
_TOOLING_ONLY_RE = re.compile(
    r"install\s+(?:(?:-U|--upgrade|-q|--quiet)\s+)*(?:(?:pip|setuptools|wheel|build|uv)\b\s*)+$"
    # "npm install --global npm@11" updates npm itself, not the project.
    r"|\b(?:npm|pnpm) (?:install|i)\b.*(?:-g|--global)\b",
    re.I,
)


# Never advice for someone's own machine: `sudo pip install` and
# `--break-system-packages` change the system's own Python. GDAL's code-check workflow
# (2026-10-22) does both, to install a citation checker, and a PR draft repeated it.
_SYSTEM_WIDE_RE = re.compile(r"\bsudo\b|--break-system-packages", re.I)
_PIP_ARGS_RE = re.compile(r"\b(?:pip3? install|-m pip install|uv pip install)\b(.*)$", re.I)
_NPM_ADD_ARGS_RE = re.compile(r"\b(?:npm (?:install|i)|pnpm (?:install|add)|yarn add)\b(.*)$", re.I)


def _installs_the_project(command: str) -> bool:
    """False for a command that only installs named tools ("pip install cffconvert")."""
    for pattern in (_PIP_ARGS_RE, _NPM_ADD_ARGS_RE):
        match = pattern.search(command)
        if not match:
            continue
        args = match.group(1).split()
        # The project itself (".", ".[test]", -e), a dependency list (-r, --group), or,
        # for npm with only flags, the dependencies in package.json.
        if any(
            a.startswith((".", "-e", "--editable", "-r", "--requirement", "--group"))
            or "requirements" in a
            for a in args
        ):
            return True
        return all(a.startswith("-") for a in args)
    return True


def ci_install_commands(workflows: dict[str, str], *, limit: int = 3) -> list[dict[str, str]]:
    """Commands CI runs to install the project and its dependencies, from `run:` steps.

    A command that only installs a named tool counts when its workflow also runs the
    tests or installs the project: a lint workflow's tools say nothing about setting up
    the project.
    """
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for path, text in workflows.items():
        for block in _run_blocks(text):
            for command in _commands(block):
                if (
                    command
                    and not command.startswith("#")
                    and _INSTALL_RE.search(command)
                    and not _TOOLING_ONLY_RE.search(command)
                    and not _SYSTEM_WIDE_RE.search(command)
                    and command not in seen
                ):
                    seen.add(command)
                    found.append({"command": _shorten(command), "source": path})
    useful = {c["source"] for c in ci_test_commands(workflows, limit=len(seen) + 50)}
    useful |= {c["source"] for c in found if _installs_the_project(c["command"])}
    return [c for c in found if c["source"] in useful][:limit]


def _run_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)(?:-\s+)?run:\s*(\|?-?|>-?)?\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue
        indent, style, rest = match.groups()
        if style:
            body = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip()
                or len(lines[index]) - len(lines[index].lstrip()) > len(indent)
            ):
                body.append(lines[index])
                index += 1
            blocks.append("\n".join(body))
            continue
        blocks.append(rest)
        index += 1
    return blocks


_CHANGELOG_TERM_RE = re.compile(
    r"(changelog|CHANGES\.(?:rst|md)|news (?:fragment|entry)|towncrier|changeset|whats_?new|release notes?)",
    re.I,
)
_ASK_RE = re.compile(
    r"\b(add|include|update|write|create|provide|need|needs|must|should|required|please|remember)\b",
    re.I,
)
_GENERATED_RE = re.compile(r"\b(automatic\w*|generated|generate[sd]?)\b", re.I)


def changelog_request(contributing: str, pr_template: str) -> str | None:
    """Evidence that contributors must write a changelog or release-notes entry.

    A heading in the pull request template counts (SymPy's "Release Notes").
    Elsewhere the sentence must ask the contributor to act and must not describe
    notes generated automatically from commits (stdlib's guide does).
    """
    for line in pr_template.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+)$", line)
        if heading and _CHANGELOG_TERM_RE.search(heading.group(1)):
            return f"The PR template has a '{heading.group(1).strip()}' section"
    for source, text in (("CONTRIBUTING", contributing), ("the PR template", pr_template)):
        flat = re.sub(r"\s+", " ", re.sub(r"<!--.*?-->", " ", text, flags=re.S))
        for sentence in re.split(r"(?<=[.!?])\s+", flat):
            term = _CHANGELOG_TERM_RE.search(sentence)
            if term and _ASK_RE.search(sentence) and not _GENERATED_RE.search(sentence):
                return f"{source} asks contributors to update '{term.group(1)}'"
    return None


MIN_COMMITS_FOR_A_RULE = 5


def conventions(
    commits: list[dict[str, Any]],
    *,
    contributing: str,
    pr_template: str,
    check_names: list[str],
    found: dict[str, Any],
) -> dict[str, Any]:
    """Rules a PR must follow: sign-off, CLA, commit style, checklist. Evidence per rule."""
    messages = [str((c.get("commit") or {}).get("message") or "") for c in commits]
    signed = sum(1 for m in messages if "Signed-off-by:" in m)
    conventional = sum(1 for m in messages if CONVENTIONAL_RE.match(m.splitlines()[0] if m else ""))
    total = len(messages)
    checks_lower = [c.lower() for c in check_names]
    text = f"{contributing}\n{pr_template}"

    dco_evidence: list[str] = []
    # "1 of the last 1 commits" is no evidence of a rule.
    if total >= MIN_COMMITS_FOR_A_RULE and signed / total >= 0.5:
        dco_evidence.append(f"{signed} of the last {total} commits carry Signed-off-by")
    if any("dco" in c for c in checks_lower):
        dco_evidence.append("a DCO status check runs on pull requests")
    if found.get("dco_file"):
        dco_evidence.append(f"{found['dco_file']} is present")
    match = re.search(
        r"(git commit -s|Signed-off-by|Developer Certificate of Origin|\bDCO\b)", text
    )
    if match:
        dco_evidence.insert(0, f"CONTRIBUTING or the PR template mentions '{match.group(1)}'")

    cla_evidence: list[str] = []
    if any(re.search(r"\bcla\b|easycla|license/cla|verify cla", c) for c in checks_lower):
        cla_evidence.append("a CLA status check runs on pull requests")
    if found.get("cla_file"):
        cla_evidence.append(f"{found['cla_file']} is present")
    if re.search(r"Contributor License Agreement|\bCLA\b", text):
        cla_evidence.append("CONTRIBUTING or the PR template mentions a CLA")

    ratio = conventional / total if total else 0.0
    style_evidence: list[str] = []
    if total:
        style_evidence.append(
            f"{conventional} of the last {total} commits use type(scope): subject"
        )
    if found.get("commitlint"):
        style_evidence.append("a commitlint or release tooling config is in the repository")
    if any(re.search(r"commitlint|semantic|conventional|pr title", c) for c in checks_lower):
        style_evidence.append("a commit or PR title check runs on pull requests")

    changelog_evidence: list[str] = []
    if found.get("news_fragments"):
        changelog_evidence.append(f"{found['news_fragments']}/ holds one entry per change")
    mention = changelog_request(contributing, pr_template)
    if mention:
        changelog_evidence.insert(0, mention)

    checklist_items = len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", pr_template, flags=re.M))
    return {
        "dco": {"required": bool(dco_evidence), "evidence": dco_evidence},
        "cla": {"required": bool(cla_evidence), "evidence": cla_evidence},
        "conventional_commits": {
            "expected": ratio >= 0.7 or bool(found.get("commitlint")),
            "ratio": round(ratio, 2),
            "evidence": style_evidence,
        },
        "changelog": {"expected": bool(changelog_evidence), "evidence": changelog_evidence},
        "pre_commit": bool(found.get("pre_commit")),
        "pr_checklist_items": checklist_items,
        "ai_disclosure_in_pr_template": bool(
            re.search(r"\bai\b.*disclos|disclos.*\bai\b", pr_template, re.I | re.S)
        ),
        "codeowners": found.get("codeowners"),
        "required_checks_seen": sorted(set(check_names))[:12],
    }


_ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_MD_LINK = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")
_MD_EMPHASIS = re.compile(r"(\*\*|__)(.+?)\1")
_MD_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>|])")
_MD_SINGLE_EMPHASIS = re.compile(r"(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])")


def _logical_lines(text: str) -> list[str]:
    """Join hard-wrapped lines, so a sentence or list item split across lines stays whole."""
    lines: list[str] = []
    in_code = in_item = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith(("```", "~~~")):
            in_code = not in_code
            lines.append("")
            continue
        is_item = _ITEM_START.match(raw) is not None
        starts_block = not stripped or stripped.startswith(("#", "|", ">")) or is_item
        # A list item continues only on an indented line; a paragraph on any line.
        continues = bool(lines and lines[-1]) and (not in_item or raw[:1].isspace())
        if in_code or starts_block or not continues:
            lines.append("" if in_code else stripped)
            in_item = is_item
        else:
            lines[-1] = f"{lines[-1]} {stripped}"
    return lines


def _plain(markdown: str) -> str:
    text = _MD_EMPHASIS.sub(r"\2", _MD_LINK.sub(r"\1", markdown))
    text = _MD_SINGLE_EMPHASIS.sub(r"\2", text).replace("`", "")
    return _MD_ESCAPE.sub(r"\1", text)  # "work on it\*" -> "work on it*"


def policy_quotes(texts: dict[str, str], *, limit: int = 8) -> list[dict[str, str]]:
    """Sentences about assignment, AI use, PR limits, and newcomers, with sources.

    Words are the project's own; wrapped lines are joined and markdown links and
    emphasis are reduced to their text.
    """
    quotes: list[dict[str, str]] = []
    seen: set[str] = set()
    for source, text in texts.items():
        cleaned = re.sub(r"<!--.*?-->", " ", text or "", flags=re.S)
        for line in _logical_lines(cleaned):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or re.match(r"^[-*]\s*\[[ xX]\]", stripped):
                continue
            stripped = re.sub(r"^[-*>\d.)\s]+", "", _plain(stripped))
            for sentence in _SENTENCE_SPLIT.split(re.sub(r"\s+", " ", stripped)):
                clean = clean_untrusted(sentence.strip(" -*#>"), limit=300)
                if not 20 <= len(clean) <= 300 or len(clean.split()) < 4 or clean in seen:
                    continue
                for kind, pattern in POLICY_PATTERNS.items():
                    if pattern.search(clean):
                        seen.add(clean)
                        quotes.append({"kind": kind, "text": clean, "source": source})
                        break
    priority = {"assignment": 0, "ai": 1, "pr_limit": 2, "first_timer": 3}
    quotes.sort(key=lambda q: priority[q["kind"]])
    return quotes[:limit]


_GATE_WORKFLOW_RE = re.compile(
    r"contribut|pr[-_.]?(?:title|check|lint|label)|pull[-_]?request|semantic|"
    r"linked[-_]?issue|issue[-_]?(?:link|check|ref)|assign|dco|cla\b|title",
    re.I,
)


def rank_gate_workflows(paths: list[str], *, skip: list[str], limit: int = 3) -> list[str]:
    """Workflow files that look like pull-request gates (title, issue link, assignment)."""
    taken = set(skip)
    return [
        p
        for p in sorted(paths)
        if p not in taken and _GATE_WORKFLOW_RE.search(p.rsplit("/", 1)[-1])
    ][:limit]


def branch_gates(rules: list[dict[str, Any]], *, branch: str) -> list[dict[str, str]]:
    """Plain-language gates from a branch's active ruleset rules, one per rule that
    changes what a contributor has to do. Rules about deleting or force-pushing the
    branch itself are left out: a contributor works on a fork."""
    gates: list[dict[str, str]] = []
    source = f"ruleset on {branch}"

    def add(gate: str) -> None:
        if gate not in (g["gate"] for g in gates):
            gates.append({"gate": gate, "source": source})

    for rule in rules:
        kind = str(rule.get("type") or "")
        params = rule.get("parameters") or {}
        if kind == "required_signatures":
            add("Commits must be signed (GPG or SSH); set up commit signing before you push")
        elif kind == "required_linear_history":
            add(f"Linear history: rebase on {branch} instead of merging it into your branch")
        elif kind == "pull_request":
            count = int(params.get("required_approving_review_count") or 0)
            parts = []
            if count:
                parts.append(f"{count} approving review{'s' if count != 1 else ''}")
            if params.get("require_code_owner_review"):
                parts.append("including a code owner")
            if parts:
                text = "Needs " + " ".join(parts)
                if params.get("dismiss_stale_reviews_on_push"):
                    text += "; pushing new commits dismisses earlier approvals"
                add(text)
            if params.get("required_review_thread_resolution"):
                add("Every review conversation must be resolved before merge")
        elif kind == "required_status_checks":
            checks = [
                str(c.get("context"))
                for c in params.get("required_status_checks") or []
                if isinstance(c, dict) and c.get("context")
            ]
            if checks:
                extra = len(checks) - 4
                shown = ", ".join(checks[:4]) + (f" and {extra} more" if extra > 0 else "")
                add(f"Required checks must pass: {shown}")
            if params.get("strict_required_status_checks_policy"):
                add(f"Your branch must be up to date with {branch} before it can merge")
        elif kind == "merge_queue":
            method = str(params.get("merge_method") or "").lower()
            add("Merged through a merge queue" + (f" ({method})" if method else ""))
        elif kind in {"commit_message_pattern", "commit_author_email_pattern"}:
            what = "Commit messages" if kind == "commit_message_pattern" else "Commit author emails"
            operator = str(params.get("operator") or "match").replace("_", " ")
            pattern = str(params.get("pattern") or "")
            label = str(params.get("name") or "").strip()
            negate = "must not" if params.get("negate") else "must"
            if pattern:
                add(f"{what} {negate} {operator} `{pattern}`" + (f" ({label})" if label else ""))
    return gates


_ISSUE_GATE_RE = re.compile(
    r"issue_assignee|issue_reference|linked[_ -]issue|check-linked-issues|"
    r"require[sd]?[_ -]linked|must (?:reference|link) an issue",
    re.I,
)
_TITLE_GATE_RE = re.compile(
    r"action-semantic-pull-request|semantic[-_ ]pull[-_ ]request|pr[-_ ]title|"
    r"conventional[-_ ]pr|commitlint.*title",
    re.I,
)


def workflow_gates(workflows: dict[str, str]) -> list[dict[str, str]]:
    """Pull-request gates that live in workflow files rather than in CONTRIBUTING."""
    gates: list[dict[str, str]] = []
    for path, text in workflows.items():
        if not text:
            continue
        if _ISSUE_GATE_RE.search(text):
            assignee = re.search(r"issue_assignee|assigned to", text, re.I)
            closes = re.search(r"close_on|close[sd]?[_ ](?:the )?(?:pr|pull)", text, re.I)
            gate = "Pull requests must reference an issue"
            if assignee:
                gate += " that is assigned to the author"
            if closes:
                gate += "; pull requests that do not are closed automatically"
            gates.append({"gate": gate, "source": path})
        if _TITLE_GATE_RE.search(text):
            gates.append(
                {"gate": "The pull request title is checked against a format", "source": path}
            )
    return gates


def ci_test_dirs_first(test_dirs: list[str], workflow_texts: dict[str, str]) -> list[str]:
    """Test folders the CI workflows name come first (ArduPilot's Tools/autotest beats a
    folder with more test-named files that CI never runs); order is otherwise kept."""
    ci_text = "\n".join(workflow_texts.values())
    return sorted(test_dirs, key=lambda d: f"{d}/" not in ci_text)


def rank_workflows(paths: list[str], *, limit: int = 2) -> list[str]:
    """Workflow files most likely to run the test suite, best first."""

    # Best first. Checks on branch names, sizes, or style run on every pull request but
    # test nothing; quality gates and pull-request workflows run the tests more often
    # than builds do.
    tiers = (
        r"assign|triage|greet|welcome|first[-_]?interaction|dependabot|codeql|lock|"
        r"\bbots?\b|[-_]bot\b|issue",
        r"convention|ratchet|size|lint|format|spell|label|stale|comment",
        r"unit",
        r"test|pytest|tox|nox",
        r"^ci\b|[._-]ci\b|\bci[._-]|check|quality|gate|verify|validate|pull[_-]?request|^pr[._-]",
        r"main|build",
        r"release|publish|deploy|docs|close|welcome",
    )
    order = (8, 7, 0, 1, 2, 3, 5)

    def priority(path: str) -> tuple[int, str]:
        name = path.rsplit("/", 1)[-1].lower()
        for pattern, rank in zip(tiers, order, strict=True):
            if re.search(pattern, name):
                return (rank, name)
        return (4, name)

    return sorted(paths, key=priority)[:limit]


def active_committers(commits: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    """People who landed commits in the sample, bots removed, most active first."""
    counts: Counter[str] = Counter()
    for commit in commits:
        author = commit.get("author") or {}
        login = str(author.get("login") or "")
        if author.get("type") == "Bot" or login.endswith("[bot]") or login.lower() in KNOWN_BOTS:
            continue
        if not login:
            # A git author name is free text that anyone can set on a commit.
            login = clean_untrusted(
                ((commit.get("commit") or {}).get("author") or {}).get("name"), limit=100
            )
        if login and not login.lower().endswith("[bot]"):
            counts[login] += 1
    return [{"login": login, "commits": n} for login, n in counts.most_common(limit)]


def codeowners_for(text: str, *, limit: int = 8) -> list[dict[str, str]]:
    """CODEOWNERS lines as (pattern, owners); last matching pattern wins on GitHub."""
    rows = []
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append({"pattern": parts[0], "owners": " ".join(parts[1:])})
    return rows[:limit]


def reading_plan(
    *,
    found: dict[str, Any],
    points: list[dict[str, str]],
    example_pr: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """An ordered reading list, each step a real path or URL."""
    steps: list[dict[str, str]] = []
    if found.get("readme"):
        steps.append({"path": found["readme"], "why": "What the project is and how to run it"})
    if found.get("contributing"):
        steps.append({"path": found["contributing"], "why": "How this project wants changes made"})
    for doc in found.get("architecture_docs") or []:
        steps.append({"path": doc, "why": "How the code is organised, in the maintainers' words"})
    for point in points[:2]:
        steps.append({"path": point["path"], "why": f"Entry point: {point['reason']}"})
    for test_dir in (found.get("test_dirs") or [])[:1]:
        steps.append(
            {"path": test_dir, "why": "How behaviour is tested; your change will need a test here"}
        )
    for workflow in rank_workflows(found.get("workflows") or [], limit=1):
        steps.append({"path": workflow, "why": "What CI runs on your pull request"})
    if example_pr:
        steps.append(
            {
                "path": str(example_pr.get("url") or ""),
                "why": f"A recently merged small PR from an outside contributor ({example_pr.get('files', '?')} files): the shape of a change that lands",
            }
        )
    return list({s["path"]: s for s in reversed(steps)}.values())[::-1]  # first of each path


def days_since(value: str | None, now: datetime | None = None) -> int | None:
    if not value:
        return None
    now = now or datetime.now(UTC)
    try:
        then = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    return (now - then).days


def since_iso(days: int, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return (now - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def codetour_from_orientation(data: dict[str, Any]) -> dict[str, Any]:
    """A CodeTour file (VS Code) that walks the reading plan, pinned to the inspected commit."""
    steps: list[dict[str, Any]] = [
        {
            "description": (
                f"Welcome to {data.get('repo')}. This tour follows the reading plan from "
                "git-into-gsoc orient: what the project is, how it wants changes made, where the "
                "code and tests live, and how CI runs the tests. Read; do not skim."
            )
        }
    ]
    for step in data.get("reading_plan") or []:
        path = str(step.get("path") or "")
        why = str(step.get("why") or "")
        if path.startswith("http"):
            steps.append({"description": f"{why}\n\n[{path}]({path})"})
        elif path in set(data.get("docs", {}).get("test_dirs") or []) or path in {
            row["path"] for row in data.get("code_map") or []
        }:
            steps.append({"directory": path, "description": why})
        else:
            steps.append({"file": path, "line": 1, "description": why})
    for row in (data.get("code_map") or [])[:6]:
        if row.get("path") in {".", ""}:
            continue
        guess = " (a guess from the name)" if row.get("purpose_is_guess") else ""
        steps.append(
            {
                "directory": row["path"],
                "description": f"{row['files']} files; purpose: {row['purpose']}{guess}.",
            }
        )
    for command in (data.get("test_commands") or [])[:1]:
        steps.append(
            {
                "description": (
                    f"Run the tests the way CI does ({command.get('source')}):\n\n"
                    f">> {command.get('command')}"
                )
            }
        )
    return {
        "$schema": "https://aka.ms/codetour-schema",
        "title": "#1 - GSoC orientation",
        "description": f"Orientation for {data.get('repo')} as of commit {data.get('as_of_commit')}",
        "ref": data.get("as_of_commit") or data.get("default_branch") or "HEAD",
        "steps": steps,
    }


def work_branch(merged: list[dict[str, Any]], *, default: str) -> dict[str, Any] | None:
    """The branch most recent merged pull requests went to, when it is not the default.

    metabrainz/listenbrainz-android merged its recent outside pull requests into `cmp`
    (a Compose Multiplatform migration) while `main` had not moved for two months: a
    newcomer who branches from `main` may fix code that is being moved.
    """
    bases = Counter(
        str((p.get("base") or {}).get("ref") or "")
        for p in merged
        if (p.get("base") or {}).get("ref")
    )
    total = sum(bases.values())
    if total < 4:
        return None
    branch, count = bases.most_common(1)[0]
    if branch == default or count * 2 < total:
        return None
    return {
        "branch": branch,
        "merged": count,
        "of": total,
        "note": (
            f"{count} of the last {total} merged pull requests went to `{branch}`, not "
            f"`{default}`. Ask the maintainers which branch new work should start from "
            "before you branch."
        ),
    }
