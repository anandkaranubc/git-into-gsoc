"""Templates for the messages a contributor writes, grounded in maintainers' words.

Each draft is a skeleton with angle-bracket placeholders, a list of fields that
must hold real evidence before the message is sent, and the rules maintainers
and the official contributor guide state, each with its source. The tool never
fills in observations it does not have; the contributor does.
"""

from __future__ import annotations

import re
from typing import Any

from git_into_gsoc.github.availability import CONTESTED_MIN_CLAIMANTS
from git_into_gsoc.text import clean_untrusted, straight_quotes

DRAFT_KINDS = ("intro", "question", "claim", "pr", "review-reply", "status", "final")

GUIDE_FIRST_CONTACT = "https://google.github.io/gsocguides/student/making-first-contact"
GUIDE_COMMUNICATION = "https://google.github.io/gsocguides/student/communication-best-practices"
GUIDE_MENTOR = "https://google.github.io/gsocguides/student/working-with-your-mentor"
GUIDE_WORK_PRODUCT = "https://developers.google.com/open-source/gsoc/help/work-product"
GUIDE_RESPONSIBILITIES = "https://developers.google.com/open-source/gsoc/help/responsibilities"
NOHELLO = "https://nohello.net/en/"
DONT_ASK_TO_ASK = "https://dontasktoask.com/"
SMART_QUESTIONS = "http://www.catb.org/~esr/faqs/smart-questions.html"
XY_PROBLEM = "https://xyproblem.info/"
PANDAS_CONTRIBUTING = "https://pandas.pydata.org/docs/development/contributing.html"
K8S_FIRST_CONTRIBUTION = "https://www.kubernetes.dev/docs/guide/first-contribution/"
GOOGLE_CL_DESCRIPTIONS = (
    "https://google.github.io/eng-practices/review/developer/cl-descriptions.html"
)
PYTHON_GSOC_BLOGS = "https://python-gsoc.org/blogs.html"
OUTREACHY_APPLICANT = "https://www.outreachy.org/docs/applicant/"

_RULES: dict[str, list[dict[str, str]]] = {
    "intro": [
        {
            "rule": "Post in the public channel. Never private-message someone you do not know without asking in public first.",
            "source": GUIDE_COMMUNICATION,
        },
        {
            "rule": "Read the channel for a few days first; bring at least a few real questions before offering opinions.",
            "source": GUIDE_FIRST_CONTACT,
        },
        {
            "rule": "Say what you want in the first message; do not send only 'hello'.",
            "source": NOHELLO,
        },
    ],
    "question": [
        {
            "rule": "Describe the goal, not just the step you are stuck on, so people can spot an XY problem.",
            "source": XY_PROBLEM,
        },
        {
            "rule": "Show what you tried and where you looked; maintainers want to see research before asking.",
            "source": SMART_QUESTIONS,
        },
        {
            "rule": "Ask the question itself; do not ask whether you may ask.",
            "source": DONT_ASK_TO_ASK,
        },
        {
            "rule": "Try for a couple of hours first, then ask; follow up once after about five days of silence.",
            "source": GUIDE_MENTOR,
        },
    ],
    "claim": [
        {
            "rule": "One comment with your intention and a short plan; do not post a bare 'can I work on this?'.",
            "source": PANDAS_CONTRIBUTING,
        },
        {
            "rule": "Use the project's own claim mechanism when it has one (for example a /assign command).",
            "source": K8S_FIRST_CONTRIBUTION,
        },
        {
            "rule": "If someone claimed it recently, pick another issue; if you stop, say so in the thread.",
            "source": PANDAS_CONTRIBUTING,
        },
    ],
    "pr": [
        {
            "rule": "The first line is short and imperative; the body says what changed and why, and names shortcomings.",
            "source": GOOGLE_CL_DESCRIPTIONS,
        },
        {
            "rule": "Every pull request costs reviewer time; keep it small, one logical change, with tests when the project expects them.",
            "source": K8S_FIRST_CONTRIBUTION,
        },
        {
            "rule": "Check for an open pull request that already does the same thing before opening yours.",
            "source": GUIDE_COMMUNICATION,
        },
    ],
    "review-reply": [
        {
            "rule": "Reply to every review comment; do not resolve threads you did not start.",
            "source": "https://arxiv.org/pdf/2302.05058",
        },
        {
            "rule": "When you do not understand a comment, say so and ask; do not guess or get defensive.",
            "source": GUIDE_MENTOR,
        },
    ],
    "status": [
        {
            "rule": "Answer the three questions every week: what you did, what is next, where you are stuck.",
            "source": PYTHON_GSOC_BLOGS,
        },
        {
            "rule": "Share completed work, next steps and blockers regularly; say early when scope must change.",
            "source": GUIDE_RESPONSIBILITIES,
        },
    ],
    "final": [
        {
            "rule": "The work product must cover goals, what you did, current state, what is left, what merged, and what you learned.",
            "source": GUIDE_WORK_PRODUCT,
        },
        {
            "rule": "Publish it as a blog post, web page, or public gist; a repository link or tarball is not accepted.",
            "source": GUIDE_WORK_PRODUCT,
        },
    ],
}

_MUST_FILL: dict[str, list[str]] = {
    "intro": [
        "What you read or ran before writing",
        "One specific question",
        "The area you care about and why",
    ],
    "question": [
        "Goal",
        "What happens (exact output)",
        "Environment and version",
        "What I tried",
        "One explicit question",
    ],
    "claim": [
        "How you reproduced it",
        "Where the cause looks to be",
        "Your plan in one or two lines",
        "When you expect a PR",
    ],
    "pr": [
        "Problem and issue link",
        "What changed and why",
        "Validation: commands run and results",
        "Duplicates checked",
    ],
    "review-reply": [
        "Which comment you are answering",
        "What you changed or why you did not",
        "A question if you are unsure",
    ],
    "status": ["What you did", "What is next", "Where you are stuck"],
    "final": [
        "Goals",
        "What you did",
        "Current state",
        "What is left",
        "Merged and unmerged links",
        "What you learned",
    ],
}

_CONVENTION_PATTERNS = [
    (
        "no_assignment",
        re.compile(
            # CircuitVerse: "Start working immediately - no need to wait for assignment".
            r"\b(?:we )?do(?:es)? not assign|don't assign|not assign(?:ed)? issues|"
            r"no (?:need to )?(?:ask for |wait for |be )?assign",
            re.I,
        ),
    ),
    (
        "command",
        re.compile(r"(?<![\w/])(/assign(?:-me)?|\.take(?:-issue)?|/take|@\w+bot claim)\b", re.I),
    ),
    # OpenMRS: "claim the issue by clicking the "Claim Issue" button" in JIRA.
    ("claim_by", re.compile(r"\bclaim (?:the|an|this) issue by ([^.\n]{3,80})", re.I)),
    # The p5.js web editor: "You have been assigned to the issue" before you start.
    (
        "wait_assigned",
        re.compile(
            r"\byou (?:have been|are|must be|should be) assigned (?:to )?the issue\b|"
            r"(?<!need to )(?<!not )(?<!n't )\bwait (?:until|to be|for) (?:a maintainer )?(?:to )?assign",
            re.I,
        ),
    ),
    (
        "comment",
        re.compile(
            r"\b(leave|post|add) a comment\b.*\b(intention|working on|claim|interest)", re.I
        ),
    ),
    # Only when the same sentence is about claiming: CircuitVerse's "Getting Help" list
    # says "Comment on the issue/PR with @username", which is how to ask for help.
    (
        "comment",
        re.compile(
            r"\bcomment (?:on|in) the issue\b(?=[^.\n]{0,100}\b(?:work(?:ing)? on|assign|claim|"
            r"take|pick))",
            re.I,
        ),
    ),
]


def claim_convention(text: str) -> dict[str, str]:
    """How this project wants issues claimed, read from its CONTRIBUTING or templates."""
    text = straight_quotes(text)
    for kind, pattern in _CONVENTION_PATTERNS:
        match = pattern.search(text)
        if match:
            if kind == "comment":
                # The whole sentence, not the verb the pattern captured ("Add").
                found = _sentence_at(text, match.start(), match.end())
            else:
                found = match.group(1) if match.groups() else match.group(0)
            # Strangers wrote this, and it is quoted in rules an assistant reads.
            found = " ".join(clean_untrusted(found, limit=200).split())
            return {"kind": kind, "text": found.strip().rstrip(".")}
    return {"kind": "unknown", "text": ""}


# The end of a sentence, with any closing quote or markdown after it ("issue".** Add).
_SENTENCE_END = re.compile(r"[.!?][*_`\"')\]]*(?=\s|$)|\n")


def _sentence_at(text: str, start: int, end: int) -> str:
    """The sentence or list item around text[start:end], without markdown."""
    left = max((m.end() for m in _SENTENCE_END.finditer(text, 0, start)), default=0)
    right = _SENTENCE_END.search(text, end)
    sentence = text[left : right.start() if right else len(text)]
    sentence = re.sub(r"^\s*(?:[-*+>]|\d+[.)])\s+", "", sentence)
    return re.sub(r"[*_`]+", "", sentence).strip()


def _intro(ctx: dict[str, Any]) -> str:
    org = ctx.get("org") or "<project>"
    channel = (ctx.get("channels") or ["<public channel>"])[0]
    year = ctx.get("year") or "<year>"
    return (
        f"In {channel}, once:\n\n"
        f"Hi, I'm <name> ({ctx.get('code_host') or 'GitHub'}: <handle>). I'm new to {org} "
        f"and preparing for GSoC {year}.\n"
        f"I read <CONTRIBUTING or the developer guide> and got <component> running on <OS>.\n"
        f"I'm interested in <area> because <one concrete reason tied to the ideas page or your own use>.\n"
        f"I'm looking at <issue URL>; before I start, <one specific question>."
    )


def _question(ctx: dict[str, Any]) -> str:
    where = (ctx.get("channels") or ["the project's public channel"])[0]
    return (
        f"In {where}:\n\n"
        "Goal: <what I am trying to achieve, not the step I am stuck on>\n"
        "What happens: <exact error or output, trimmed, no private data>\n"
        "Expected: <what I expected instead>\n"
        "Environment: <OS, versions, commit>\n"
        "What I tried: <two or three things, including the docs or threads I searched>\n"
        "Question: <one explicit question>"
    )


def _claim(ctx: dict[str, Any]) -> str:
    issue = ctx.get("issue") or {}
    ref = f"{issue.get('repo')}#{issue.get('number')}" if issue.get("number") else "<owner/repo#N>"
    files = ", ".join(ctx.get("files") or []) or "<file or function>"
    convention = ctx.get("claim_convention") or {}
    earlier = issue.get("earlier_claims") or []
    opening = "I'd like to work on this."
    if earlier and (issue.get("earlier_claim_count") or len(earlier)) < CONTESTED_MIN_CLAIMANTS:
        # One or two people asked and nothing followed: ask the newest first. With more,
        # the plan below has to carry the comment (see the warning).
        who = earlier[0]
        said = "were told yes" if who.get("granted") else "asked to work on this"
        opening = (
            f"@{who['login']}, you {said} {who['days_ago']} days ago. "
            "Are you still on it? If not, I'd like to take it."
        )
    lines = [
        f"On {ref}, one comment:",
        "",
        f"{opening} I reproduced it on <commit> with <steps>.",
        f"The cause looks to be in {files}: <one sentence hypothesis>.",
        "Plan: <one or two lines>. I expect to open a PR by <date>.",
        "If someone is already on it, tell me and I'll pick another issue.",
    ]
    if convention.get("kind") == "command":
        lines.append(f"{convention['text']}")
    elif convention.get("kind") == "no_assignment":
        lines.insert(
            1, "(This project does not assign issues: open the PR when ready instead of waiting.)"
        )
    elif convention.get("kind") == "wait_assigned":
        lines.append("")
        lines.append("(This project assigns issues: wait until a maintainer assigns you.)")
    if any("assigned to the author" in gate for gate in ctx.get("gates") or []):
        lines.append("")
        lines.append(
            "(This project closes pull requests from people not assigned to the issue: "
            "wait until a maintainer assigns you before you open one.)"
        )
    return "\n".join(lines)


def _pr(ctx: dict[str, Any]) -> str:
    issue = ctx.get("issue") or {}
    ref = f"#{issue.get('number')}" if issue.get("number") else "#<issue>"
    test_cmd = (ctx.get("test_commands") or ["<the project's test command>"])[0]
    lines = []
    if ctx.get("pr_template_path"):
        lines += [
            f"Start from the project's own template, {ctx['pr_template_path']}, and fill in "
            "every section. Make sure it covers:",
            "",
        ]
    lines += [
        "Title: <imperative, under 70 characters, in the project's style>",
        "",
        f"Problem: <what was broken or confusing>. Fixes {ref}.",
        "Change: <what changed and why; alternatives considered; known shortcomings>",
        f"Validation: ran `{test_cmd}`; <result>. <new or updated tests>",
        "Duplicates checked: <searched open PRs for ...; none found / #123 differs because ...>",
        "Review guidance: <where to look first; one thing I am unsure about>",
    ]
    if ctx.get("ai_disclosure"):
        lines.append("AI disclosure: <tools used and for what, as the project's template asks>")
    if ctx.get("dco"):
        lines.append("(Commits signed off with git commit -s, as this project requires.)")
    gates = ctx.get("gates") or []
    if gates:
        lines.append("")
        lines.append("This repository also requires:")
        lines.extend(f"  - {gate}" for gate in gates)
    lines.extend(_setup_commands(ctx))
    return "\n".join(lines)


_NPM_DEFAULT_TEST = "no test specified"


def manifest_commands(names: set[str], *, package_json: str | None) -> tuple[list[str], str | None]:
    """Install commands and a test (or build) command from a project's own manifest files.

    Used when CI shows none. `names` are the files and folders at the repository root.
    """
    import json

    if "package.json" in names:
        runner = "yarn" if "yarn.lock" in names else "pnpm" if "pnpm-lock.yaml" in names else "npm"
        install = {"npm": "npm ci" if "package-lock.json" in names else "npm install"}.get(
            runner, f"{runner} install"
        )
        try:
            scripts = json.loads(package_json or "{}").get("scripts") or {}
        except (ValueError, AttributeError):
            scripts = {}
        test = scripts.get("test")
        if test and _NPM_DEFAULT_TEST not in str(test):
            return [install], f"{runner} test"
        if scripts.get("build"):
            return [install], f"{runner} run build"
        return [install], None
    if names & {"pyproject.toml", "setup.py", "setup.cfg"}:
        return ["pip install -e ."], ("pytest" if names & {"tests", "test"} else None)
    if "Cargo.toml" in names:
        return [], "cargo test"
    if "go.mod" in names:
        return [], "go test ./..."
    if "Gemfile" in names:
        return ["bundle install"], None
    return [], None


# Installing a Node project's dependencies, however it is spelled: "npm ci", "npm
# clean-install", or "npm install" with only flags. CircuitVerse's CI has "npm ci" in one
# job and "npm install" in another; listing both says to install twice.
_NODE_DEPS_RE = re.compile(
    r"^(?:(yarn)(?: install)?|(npm|pnpm) (?:ci|clean-install|install|i))(?: -\S+)*$"
)


def _distinct(commands: list[str] | None, limit: int = 2) -> list[str]:
    """One command per tool and action: "npm clean-install --ignore-scripts" repeats
    "npm clean-install", and "npm install" repeats "npm ci"."""
    seen: set[str] = set()
    out: list[str] = []
    for command in commands or []:
        node = _NODE_DEPS_RE.match(command)
        tool = node and (node.group(1) or node.group(2))
        key = f"{tool} dependencies" if tool else " ".join(command.split()[:2])
        if key not in seen:
            seen.add(key)
            out.append(command)
    return out[:limit]


def _from(ctx: dict[str, Any]) -> str:
    source = ctx.get("install_source") or ctx.get("commands_source")
    return f"(from {source})" if source and source != "CI" else "as CI does"


def _venv_line(ctx: dict[str, Any]) -> list[str]:
    """A private Python environment first: many systems refuse a global pip install."""
    if not any(re.search(r"\bpip3? install\b", c) for c in ctx.get("install_commands") or []):
        return []
    return [
        "  python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate"
    ]


def _lockfile_line(ctx: dict[str, Any]) -> list[str]:
    """What to do when a guessed `npm ci` meets a lock file the project let go stale.

    CI would fail too if its own `npm ci` hit that, so this is only for commands
    read from package.json. ruxailab/web-eye-tracker-front was such a case.
    """
    if (ctx.get("install_source") or ctx.get("commands_source")) == "CI":
        return []
    if "npm ci" not in (ctx.get("install_commands") or []):
        return []
    return [
        "  # if npm ci says the lock file is out of sync: run npm install instead, and run",
        "  # git checkout -- package-lock.json before you commit so that change stays out",
    ]


def _setup_commands(ctx: dict[str, Any]) -> list[str]:
    """The exact git commands for a first pull request, with the real default branch."""
    repo = str(ctx.get("repo") or "")
    if "/" not in repo:
        return []
    name = repo.rsplit("/", 1)[-1]
    handle = ctx.get("handle") or "<your-github-username>"
    number = (ctx.get("issue") or {}).get("number")
    branch = f"fix-{number}-<short-name>" if number else "<short-branch-name>"
    base = ctx.get("default_branch") or "<default branch>"
    test_cmd = (
        ctx.get("test_commands")
        or ["<no test command found; ask the maintainers how they test changes>"]
    )[0]
    return [
        "",
        "Before you start, once:",
        f"  git clone https://github.com/{handle}/{name}.git   # after forking {repo} on GitHub",
        f"  cd {name} && git remote add upstream https://github.com/{repo}.git && git fetch upstream",
        f"  git switch -c {branch} upstream/{base}",
        *_venv_line(ctx),
        *(f"  {cmd}   # install {_from(ctx)}" for cmd in _distinct(ctx.get("install_commands"))),
        *_lockfile_line(ctx),
        f"  {test_cmd}"
        + (
            ""
            if not ctx.get("test_commands")
            else "   # no test command found; at least check it builds"
            if ctx.get("test_is_build")
            else "   # run the tests once before changing anything"
        ),
        "When the change is ready:",
        f"  git push -u origin {branch}   # then open the pull request against {base}",
    ]


def _review_reply(ctx: dict[str, Any]) -> str:
    return (
        "Under each review comment:\n\n"
        "Done in <commit>: <what changed>.\n"
        "or\n"
        "I kept this as is because <reason with evidence>; happy to change it if you prefer <alternative>.\n"
        "or\n"
        "I don't follow this one. Do you mean <reading A> or <reading B>?"
    )


def _status(ctx: dict[str, Any]) -> str:
    log = ctx.get("log") or {}
    return (
        f"Week of <date>\n\n"
        f"What I did: {log.get('done') or '<work finished, with links>'}\n"
        f"What is next: {log.get('next_step') or '<next small step>'}\n"
        f"Where I am stuck: {log.get('stuck') or '<blocker, or none>'}"
        + (f"\nGoal was: {log['goal']}" if log.get("goal") else "")
    )


def _final(ctx: dict[str, Any]) -> str:
    merged = ctx.get("merged") or []
    links = "\n".join(f"- {m}" for m in merged) or "- <merged PR links>"
    return (
        "# <Project title> (GSoC <year>, <organization>)\n\n"
        "## Goals\n<what the project set out to do>\n\n"
        "## What I did\n<the work, in order, with links>\n\n"
        "## Current state\n<what works today>\n\n"
        "## What is left\n<remaining work and known gaps>\n\n"
        f"## Merged\n{links}\n\n## Not merged yet\n- <open PR links and why>\n\n"
        "## Challenges and what I learned\n<two or three honest paragraphs>"
    )


_RENDERERS = {
    "intro": _intro,
    "question": _question,
    "claim": _claim,
    "pr": _pr,
    "review-reply": _review_reply,
    "status": _status,
    "final": _final,
}


def _project_rules(kind: str, ctx: dict[str, Any]) -> list[dict[str, str]]:
    """What this project's own guide says, before the general rules.

    A blind test passed --repo and got the same pandas and Kubernetes rules as without
    it. With a repository, the first rule now says what its contributing guide says
    about claiming, or that it says nothing.
    """
    if kind != "claim" or "claim_convention" not in ctx:
        return []
    convention = ctx.get("claim_convention") or {}
    source = str(ctx.get("contributing_url") or "")
    said = convention.get("text", "")
    if convention.get("kind") == "command":
        rule = f"This project's contributing guide says to claim an issue with {said}."
    elif convention.get("kind") == "no_assignment":
        rule = (
            "This project's contributing guide says it does not assign issues: open the "
            "pull request when it is ready instead of waiting."
        )
    elif convention.get("kind") == "comment":
        rule = f'This project\'s contributing guide says: "{said}". Do that, with your plan.'
    elif convention.get("kind") == "claim_by":
        rule = f"This project's contributing guide says to claim an issue by {said}."
    elif convention.get("kind") == "wait_assigned":
        rule = (
            "This project's contributing guide says to wait until a maintainer assigns you "
            "before you start work."
        )
    elif convention.get("kind") == "unread":
        # A rate limit is not "no guide": the rule may be there, unread.
        rule = (
            f"GitHub did not answer for this project's {said}, so its rule for claiming an "
            "issue was not read. Read its contributing guide on GitHub, if it has one, "
            "before you claim, or run this again later."
        )
        source = source or "not read: GitHub did not answer"
    elif source:
        rule = (
            "This project's contributing guide does not say how to claim an issue. Post one "
            "comment with your plan in the issue, and follow what maintainers answer there."
        )
    else:
        rule = (
            "This project has no contributing guide that says how to claim an issue. Post "
            "one comment with your plan in the issue, and follow what maintainers answer."
        )
    return [{"rule": rule, "source": source or "no contributing guide found", "scope": "project"}]


def render_draft(kind: str, *, context: dict[str, Any]) -> dict[str, Any]:
    """The template, the fields that must be filled, and the sourced rules for one
    kind of draft. Raises ValueError for a kind that is not in DRAFT_KINDS."""
    if kind not in _RENDERERS:
        raise ValueError(f"Unknown draft kind: {kind}. Choose one of {', '.join(DRAFT_KINDS)}.")
    general = [{**rule, "scope": "general"} for rule in _RULES[kind]]
    return {
        "kind": kind,
        "template": _RENDERERS[kind](context),
        "must_fill": list(_MUST_FILL[kind]),
        "rules": [*_project_rules(kind, context), *general],
        "note": (
            "Replace every <placeholder> with your own observation. Send nothing you cannot "
            "back up; reviewers read the same public history you do."
        ),
    }


# ---------------------------------------------------------------- checking a message

# The angle-bracket placeholders the templates above use, plus the proposal
# checker's patterns. Links and email addresses in angle brackets are not placeholders.
_ANGLE_PLACEHOLDER_RE = re.compile(r"<(?!https?:|/|!--)[A-Za-z][^<>\n@]{1,80}>")
_ASSISTANT_TELLS = (
    "certainly!",
    "great question",
    "i hope this message finds you",
    "i hope this email finds you",
    "i hope you are doing well",
    "feel free to reach out",
    "let me know if you have any questions",
    "i'd be happy to help",
    "here's a revised version",
    "as requested, here is",
)
_GREETING_ONLY_RE = re.compile(r"^\s*(?:hi|hello|hey|greetings|good (?:morning|evening))\b", re.I)
_BARE_CLAIM_RE = re.compile(
    r"\b(?:can|could|may) i (?:work on|take|pick up)\b|\bassign (?:it|this|me)\b|\bi want to work on\b",
    re.I,
)
_PLAN_RE = re.compile(
    r"\b(?:plan|approach|i(?:'ll| will|'d| would) (?:change|add|fix|update|start)|the cause|reproduced)\b",
    re.I,
)
_TRIED_RE = re.compile(r"\b(?:tried|attempted|searched|checked|looked at|ran|read)\b", re.I)
# Signs the writer looked at this issue, beyond the words the plan check knows: a file,
# a line, a code span or a camelCase name (frameCount, not iOS or macOS), a cause, a concrete next step, or a fix ready.
_LOOKED_RE = re.compile(
    r"`[^`\n]+`|\b[\w/-]+\.(?:py|js|ts|tsx|jsx|java|kt|c|cc|cpp|h|go|rs|rb|php|css|scss|html|"
    r"md|rst|yml|yaml|json|toml)\b|\bline \d+\b|\b[a-z]{2,}[A-Z][a-z]\w*\b|root cause|investigated|"
    r"\bready (?:locally|to open)\b|\b(?:fix|fixes|change|patch)(?:es)? ready\b|"
    r"(?i:\bI(?:'ve| have) (?:also |already )?(?:made|added|fixed|implemented|written|opened))\b|"
    r"\b(?:I'll|I will|I'd|I would|I can)\s+(?:\w+\s+){0,2}?(?:trace|track down|investigate|"
    r"implement|match|keep|adjust|rename|replace|move|remove|write|refactor|look into|"
    r"handle|test)\b|\bby (?:adding|keeping|changing|returning|using|replacing|moving|"
    r"removing|renaming|checking)\b|\b\d\. \w+ing\b",
)
_ASK_TO_ASK_RE = re.compile(r"\b(?:can i ask|may i ask|anyone (?:here|around|online))\b", re.I)
_PRIVATE_RE = re.compile(r"\b(?:dm me|direct message|message me privately|private message)\b", re.I)
_ISSUE_REF_RE = re.compile(r"#\d+|/issues/\d+")
_VALIDATION_RE = re.compile(r"\b(?:test(?:s|ed)?|pytest|ran|verified|reproduc\w*)\b", re.I)
_FINAL_SECTIONS = ("goal", "what i did", "current state", "what is left", "learn")


def _finding(fid: str, status: str, title: str, detail: str, source: str = "") -> dict[str, str]:
    return {"id": fid, "status": status, "title": title, "detail": detail, "source": source}


def check_message(kind: str, text: str) -> dict[str, Any]:
    """Check a message the contributor wrote against the rules `draft` gives for its kind.

    Never rewrites anything. Each finding names the rule and its source, so the
    person fixes the message in their own words. Idea from ContribOS's `tone`.
    """
    from git_into_gsoc.proposal import buzzwords, generic_phrases, placeholders, word_count

    if kind not in _RENDERERS:
        raise ValueError(f"Unknown draft kind: {kind}. Choose one of {', '.join(DRAFT_KINDS)}.")
    body = straight_quotes(text)
    lower = body.lower()
    words = word_count(body)
    findings: list[dict[str, str]] = []

    leftovers = list(dict.fromkeys([*placeholders(body), *_ANGLE_PLACEHOLDER_RE.findall(body)]))
    if leftovers:
        findings.append(
            _finding(
                "placeholders",
                "fail",
                f"{len(leftovers)} placeholder(s) still in the text",
                ", ".join(leftovers[:3])
                + ". Replace each with your own observation, or delete it.",
            )
        )
    tells = [t for t in _ASSISTANT_TELLS if t in lower] + generic_phrases(body) + buzzwords(body)
    if tells:
        findings.append(
            _finding(
                "machine_tone",
                "warn",
                "Phrases that read as machine-written",
                ", ".join(dict.fromkeys(tells[:5]))
                + ". Say it plainly, the way you would to a person.",
                "https://developers.google.com/open-source/gsoc/resources/ai_guidance",
            )
        )

    if kind == "intro":
        if words < 12 and _GREETING_ONLY_RE.match(body):
            findings.append(
                _finding(
                    "greeting_only",
                    "fail",
                    "Only a greeting",
                    "Say who you are, what you read or ran, and your question in the same message.",
                    NOHELLO,
                )
            )
        if "?" not in body:
            findings.append(
                _finding(
                    "question",
                    "warn",
                    "No question",
                    "End with one specific question; it gives people a reason to reply.",
                    GUIDE_FIRST_CONTACT,
                )
            )
        if words > 150:
            findings.append(
                _finding(
                    "length",
                    "warn",
                    f"Long for a first message ({words} words)",
                    "Keep it to a few sentences; details can follow when someone replies.",
                    GUIDE_FIRST_CONTACT,
                )
            )
        if _PRIVATE_RE.search(body):
            findings.append(
                _finding(
                    "public",
                    "warn",
                    "Asks to move to private messages",
                    "Keep the conversation in the public channel.",
                    GUIDE_COMMUNICATION,
                )
            )
    elif kind == "question":
        if "?" not in body:
            findings.append(
                _finding(
                    "question",
                    "fail",
                    "No question in the message",
                    "State the question itself, in one sentence.",
                    DONT_ASK_TO_ASK,
                )
            )
        if _ASK_TO_ASK_RE.search(body):
            findings.append(
                _finding(
                    "ask_to_ask",
                    "warn",
                    "Asks whether you may ask",
                    "Ask the question directly.",
                    DONT_ASK_TO_ASK,
                )
            )
        if not _TRIED_RE.search(body):
            findings.append(
                _finding(
                    "tried",
                    "warn",
                    "Does not say what you tried",
                    "List what you tried and where you looked.",
                    SMART_QUESTIONS,
                )
            )
    elif kind == "claim":
        # Skills and enthusiasm do not make a request less bare: "I have strong skills in
        # Python, ML, DL ... Kindly assign this issue to me" says nothing about the issue.
        looked = _PLAN_RE.search(body) or _TRIED_RE.search(body) or _LOOKED_RE.search(body)
        if _BARE_CLAIM_RE.search(body) and (words < 25 or not looked):
            findings.append(
                _finding(
                    "bare_claim",
                    "fail",
                    "A bare request to work on it",
                    "Add how you reproduced it and a one or two line plan. A list of your "
                    "skills does not tell the maintainer how you would fix this issue.",
                    PANDAS_CONTRIBUTING,
                )
            )
        elif not _PLAN_RE.search(body):
            findings.append(
                _finding(
                    "plan",
                    "warn",
                    "No plan",
                    "Say where the cause looks to be and what you would change.",
                    PANDAS_CONTRIBUTING,
                )
            )
    elif kind == "pr":
        if not _ISSUE_REF_RE.search(body):
            findings.append(
                _finding(
                    "issue_link",
                    "warn",
                    "No linked issue",
                    "Add 'Fixes #N' so reviewers have the context.",
                    GOOGLE_CL_DESCRIPTIONS,
                )
            )
        if not _VALIDATION_RE.search(body):
            findings.append(
                _finding(
                    "validation",
                    "warn",
                    "Does not say how you tested it",
                    "Name the commands you ran and what they showed.",
                    K8S_FIRST_CONTRIBUTION,
                )
            )
    elif kind == "status":
        for label, pattern in (
            ("what you did", r"\b(?:did|done|finished|merged|opened)\b"),
            ("what is next", r"\bnext\b"),
            ("where you are stuck", r"\b(?:stuck|blocked|blocker|none)\b"),
        ):
            if not re.search(pattern, lower):
                findings.append(
                    _finding(
                        "three_questions",
                        "warn",
                        f"Does not say {label}",
                        "Weekly updates answer what you did, what is next, and where you are stuck.",
                        PYTHON_GSOC_BLOGS,
                    )
                )
    elif kind == "final":
        missing = [s for s in _FINAL_SECTIONS if s not in lower]
        if missing:
            findings.append(
                _finding(
                    "sections",
                    "warn",
                    "Missing parts of the final report",
                    ", ".join(missing) + ".",
                    GUIDE_WORK_PRODUCT,
                )
            )

    fails = sum(1 for f in findings if f["status"] == "fail")
    warns = sum(1 for f in findings if f["status"] == "warn")
    if fails:
        verdict = f"Fix {fails} problem(s) before sending."
    elif warns:
        verdict = "No blockers. Read the warnings before sending."
    else:
        verdict = "No problems found by these checks. Read it once more as the person receiving it."
    return {"kind": kind, "words": words, "findings": findings, "verdict": verdict}
