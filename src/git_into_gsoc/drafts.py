"""Templates for the messages a contributor writes, grounded in maintainers' words.

Each draft is a skeleton with angle-bracket placeholders, a list of fields that
must hold real evidence before the message is sent, and the rules maintainers
and the official contributor guide state, each with its source. The tool never
fills in observations it does not have; the contributor does.
"""

from __future__ import annotations

import re
from typing import Any

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
            r"\b(?:we )?do(?:es)? not assign|don't assign|not assign(?:ed)? issues|no (?:need to )?(?:ask for )?assign",
            re.I,
        ),
    ),
    (
        "command",
        re.compile(r"(?<![\w/])(/assign(?:-me)?|\.take(?:-issue)?|/take|@\w+bot claim)\b", re.I),
    ),
    (
        "comment",
        re.compile(
            r"\b(leave|post|add) a comment\b.*\b(intention|working on|claim|interest)", re.I
        ),
    ),
    ("comment", re.compile(r"\bcomment (?:on|in) the issue\b", re.I)),
]


def claim_convention(text: str) -> dict[str, str]:
    """How this project wants issues claimed, read from its CONTRIBUTING or templates."""
    for kind, pattern in _CONVENTION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            found = match.group(1) if match.groups() else match.group(0)
            return {"kind": kind, "text": found.strip()}
    return {"kind": "unknown", "text": ""}


def _intro(ctx: dict[str, Any]) -> str:
    org = ctx.get("org") or "<project>"
    channel = (ctx.get("channels") or ["<public channel>"])[0]
    year = ctx.get("year") or "<year>"
    return (
        f"In {channel}, once:\n\n"
        f"Hi, I'm <name> (GitHub: <handle>). I'm new to {org} and preparing for GSoC {year}.\n"
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
    lines = [
        f"On {ref}, one comment:",
        "",
        "I'd like to work on this. I reproduced it on <commit> with <steps>.",
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
    return "\n".join(lines)


def _pr(ctx: dict[str, Any]) -> str:
    issue = ctx.get("issue") or {}
    ref = f"#{issue.get('number')}" if issue.get("number") else "#<issue>"
    test_cmd = (ctx.get("test_commands") or ["<the project's test command>"])[0]
    lines = [
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
        lines.append("This repository's branch rules also require:")
        lines.extend(f"  - {gate}" for gate in gates)
    lines.extend(_setup_commands(ctx))
    return "\n".join(lines)


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
    test_cmd = (ctx.get("test_commands") or ["<the project's test command>"])[0]
    return [
        "",
        "Before you start, once:",
        f"  git clone https://github.com/{handle}/{name}.git   # after forking {repo} on GitHub",
        f"  cd {name} && git remote add upstream https://github.com/{repo}.git && git fetch upstream",
        f"  git switch -c {branch} upstream/{base}",
        f"  {test_cmd}   # run the tests once before changing anything",
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


def render_draft(kind: str, *, context: dict[str, Any]) -> dict[str, Any]:
    if kind not in _RENDERERS:
        raise ValueError(f"Unknown draft kind: {kind}. Choose one of {', '.join(DRAFT_KINDS)}.")
    return {
        "kind": kind,
        "template": _RENDERERS[kind](context),
        "must_fill": list(_MUST_FILL[kind]),
        "rules": [dict(rule) for rule in _RULES[kind]],
        "note": (
            "Replace every <placeholder> with your own observation. Send nothing you cannot "
            "back up; reviewers read the same public history you do."
        ),
    }
