"""Check a draft GSoC proposal for the things organizations reject on.

Pure text analysis (sections, links, timeline detail, specificity, generic
phrasing, length) plus optional verification of linked pull requests against
GitHub. It never rewrites the proposal; every finding says what is missing or
weak and why mentors care, so the author can fix it in their own voice.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

from git_into_gsoc.text import straight_quotes

Status = Literal["pass", "warn", "fail"]

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "synopsis": (
        "synopsis",
        "abstract",
        "summary",
        "overview",
        "introduction",
        "the problem",
        "project idea",
        "project description",
        "what i want to do",
        "thing i want to do",
    ),
    "benefits": ("benefit", "impact", "motivation", "why this matters", "value"),
    "deliverables": ("deliverable", "goals", "scope", "outcome", "what i will build"),
    "timeline": ("timeline", "schedule", "milestone", "weekly plan", "work plan"),
    "about": ("about me", "about myself", "biograph", "background", "who am i", "experience"),
    "contributions": (
        "contribution",
        "prior work",
        "previous work",
        "pull request",
        "my prs",
        "work done",
    ),
    "ai_statement": ("ai usage", "use of ai", "ai tools", "ai assistance", "ai policy", "llm"),
    "availability": ("availability", "commitment", "hours per week", "other commitments"),
}
REQUIRED_SECTIONS = ("synopsis", "deliverables", "timeline", "about")
RECOMMENDED_SECTIONS = ("benefits", "contributions", "availability")
SECTION_NAMES = {"about": "about you", "ai_statement": "AI use"}
# What Google's proposal guide says about each required section.
_REQUIRED_WHY = {
    "synopsis": "Google's guide lists a synopsis.",
    "deliverables": "Google's guide lists deliverables.",
    "timeline": "Google's guide asks for milestones with dates under the deliverables.",
    "about": "Google's guide lists biographical information.",
}
# Why each recommended section helps, and whether Google's guide names it.
_RECOMMENDED_WHY = {
    "benefits": "Google's guide lists 'Benefits to Community'.",
    "contributions": (
        "Link the pull requests and issues you worked on in this organization; "
        "`git-into-gsoc contributions --org NAME` collects them."
    ),
    "availability": (
        "Say how many hours a week you can give and what else you have on, so mentors "
        "can judge your timeline."
    ),
}

GENERIC_PHRASES = (
    "i am passionate about",
    "i am very passionate",
    "passionate and",
    "highly motivated",
    "self-motivated",
    "quick learner",
    "team player",
    "hard-working",
    "fast-paced world",
    "cutting-edge",
    "cutting edge",
    "state-of-the-art",
    "leverage",
    "delve",
    "in today's",
    "in the ever-evolving",
    "it is worth noting",
    "in conclusion",
    "i would be honored",
    "game-changer",
    "seamless",
    "robust and scalable",
    "unlock the potential",
    "testament to",
    "tapestry",
    "as an ai",
    "as a language model",
    "make the world a better place",
    "fast learner",
    "hard worker",
    "hardworking",
    "amazing community",
)

PLACEHOLDER_RE = re.compile(
    r"\[(?:your|insert|add|name|org|project|date|mentor)[^\]]*\]|<(?:insert|your|add)[^>]*>"
    r"|\bTODO\b|\bTBD\b|\bXXX\b|lorem ipsum|\{\{[^}]+\}\}",
    re.IGNORECASE,
)
BUZZWORDS = (
    "revolutioni",
    "groundbreaking",
    "innovative solution",
    "transform the way",
    "next-generation",
    "world-class",
    "best-in-class",
    "paradigm",
    "synerg",
    "holistic",
)
SPAM_GUIDANCE_URL = "https://developers.google.com/open-source/gsoc/resources/spam_proposals"
PROPOSAL_GUIDE_URL = "https://google.github.io/gsocguides/student/writing-a-proposal"

_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_GITHUB_LINK_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)/(pull|issues|commit|discussions)/([0-9a-f]+)",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+(.+?)\s*#*$|\*\*([^*]{3,80})\*\*:?\s*$|([A-Z][^\n]{2,60}):\s*$)"
)
# A heading typed as its own short line, as in a Google Doc pasted into a file:
# "Timeline", "2. About me", up to eight words. Only counts when it names a known section.
_PLAIN_HEADING_RE = re.compile(r"^(?:\d{1,2}[.)]\s*)?([A-Z][A-Za-z&/'() -]{2,59})$")
_WEEK_RE = re.compile(
    r"\b(?:week\s*\d+|weeks?\s*\d+\s*(?:-|to|\u2013)\s*\d+|w\d{1,2}\b|"
    r"(?:may|june|july|august|september|october)\s+\d{1,2})",
    re.IGNORECASE,
)
_CONCRETE_RE = re.compile(
    r"`[^`\n]+`|\b[\w./-]+\.(?:py|js|ts|tsx|rs|go|c|cc|cpp|h|java|kt|rb|md|toml|yaml|yml|json)\b"
    r"|\b\w+\(\)|#\d{2,}|/(?:-/)?(?:issues|merge_requests|pull)/\d+"
)
# A GitLab merge request or issue on any host: gitlab.com, gitlab.gnome.org, invent.kde.org.
_OTHER_HOST_LINK_RE = re.compile(
    r"https://([A-Za-z0-9.-]+\.[A-Za-z]{2,})/((?:[\w.-]+/)+?[\w.-]+)/-/(merge_requests|issues)/(\d+)"
)
_AVAILABILITY_RE = re.compile(r"\bhours?\s*(?:per|a|/)\s*week\b|\bh\s*/\s*week\b", re.I)
MAX_MR_LOOKUPS = 5
_WORD_RE = re.compile(r"[A-Za-z0-9'\u2019-]+")


@dataclass
class Finding:
    id: str
    status: Status
    title: str
    detail: str


@dataclass
class LinkEvidence:
    url: str
    kind: str  # pull | issue | commit | discussion
    repo: str
    number: str
    verified: bool = False
    author: str | None = None
    state: str | None = None
    note: str = ""


def headings(text: str) -> list[str]:
    """Headings in the text, lower-cased: markdown headings, bold lines, "Title:"
    lines, and a short plain line that names a known section."""
    found: list[str] = []
    keys = [k for group in SECTION_KEYWORDS.values() for k in group]
    for line in text.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            found.append(next(g for g in match.groups() if g).strip().lower())
            continue
        plain = _PLAIN_HEADING_RE.match(line.strip())
        if plain and len(plain.group(1).split()) <= 8:
            title = plain.group(1).strip().lower()
            if any(k in title for k in keys):
                found.append(title)
    return found


def detect_sections(text: str) -> dict[str, str | None]:
    """Map each known section to the heading that covers it, or None."""
    heads = headings(text)
    out: dict[str, str | None] = {}
    for section, keys in SECTION_KEYWORDS.items():
        out[section] = next((h for h in heads if any(k in h for k in keys)), None)
    return out


def github_links(text: str) -> list[LinkEvidence]:
    seen: set[str] = set()
    out: list[LinkEvidence] = []
    for url in _URL_RE.findall(text):
        url = url.rstrip(".,;:'\"")
        match = _GITHUB_LINK_RE.match(url)
        if not match or url.lower() in seen:
            continue
        seen.add(url.lower())
        owner, repo, kind, number = match.groups()
        out.append(
            LinkEvidence(
                url=url,
                kind={"pull": "pull", "issues": "issue", "commit": "commit"}.get(
                    kind.lower(), "discussion"
                ),
                repo=f"{owner}/{repo}",
                number=number,
            )
        )
    return out


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def generic_phrases(text: str) -> list[str]:
    lower = straight_quotes(text).lower()  # a curly apostrophe matches too
    return [p for p in GENERIC_PHRASES if p in lower]


def buzzwords(text: str) -> list[str]:
    lower = straight_quotes(text).lower()
    return [b for b in BUZZWORDS if b in lower]


def placeholders(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in PLACEHOLDER_RE.finditer(text)))


def _shingles(text: str, size: int = 8) -> set[tuple[str, ...]]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return {tuple(words[i : i + size]) for i in range(0, max(0, len(words) - size + 1))}


def mirrored_fraction(proposal: str, ideas_text: str, size: int = 8) -> float:
    """Share of the proposal's 8-word sequences that appear verbatim in the ideas page."""
    mine = _shingles(proposal, size)
    if not mine:
        return 0.0
    theirs = _shingles(ideas_text, size)
    return len(mine & theirs) / len(mine)


def timeline_entries(text: str) -> int:
    return len({m.lower() for m in _WEEK_RE.findall(text)})


def concrete_references(text: str) -> int:
    return len(set(_CONCRETE_RE.findall(text)))


PullLookup = Callable[[str, int], dict[str, Any] | None]


def other_host_links(text: str) -> list[LinkEvidence]:
    """GitLab merge request and issue links, on gitlab.com or a project's own GitLab."""
    seen: set[str] = set()
    out: list[LinkEvidence] = []
    for match in _OTHER_HOST_LINK_RE.finditer(text):
        url = match.group(0)
        if url.lower() in seen or match.group(1).lower() in {"github.com", "www.github.com"}:
            continue
        seen.add(url.lower())
        host, path, kind, number = match.groups()
        out.append(
            LinkEvidence(
                url=url,
                kind="merge_request" if kind == "merge_requests" else "issue",
                repo=f"{host}/{path}",
                number=number,
            )
        )
    return out


MergeRequestLookup = Callable[[str, str, int], dict[str, Any] | None]


def verify_merge_requests(
    links: list[LinkEvidence], *, lookup: MergeRequestLookup, github_user: str | None
) -> None:
    """Fill in author and state for GitLab merge requests, via `lookup(host, path, iid)`.

    A simulated contributor linked someone else's GNOME merge request as "My MR" and
    nothing noticed. Usernames on GitLab can differ from GitHub ones, so a mismatch
    says so instead of calling the link false.
    """
    checked = 0
    for link in links:
        if link.kind != "merge_request" or checked >= MAX_MR_LOOKUPS:
            continue
        checked += 1
        host, path = link.repo.split("/", 1)
        data = lookup(host, path, int(link.number))
        if not data:
            link.note = "could not fetch (private, deleted, not GitLab, or rate limited)"
            continue
        link.verified = True
        link.author = (data.get("author") or {}).get("username")
        state = str(data.get("state") or "unknown")
        link.state = "open" if state == "opened" else state
        if github_user and link.author and link.author.lower() != github_user.lower():
            link.note = (
                f"authored by @{link.author} on {host}, not @{github_user} (ignore this if "
                "your username there is different)"
            )


def verify_links(
    links: list[LinkEvidence], *, lookup: PullLookup, github_user: str | None, limit: int = 8
) -> list[LinkEvidence]:
    """Fill in author and state for pull-request links using ``lookup(repo, number)``."""
    checked = 0
    for link in links:
        if link.kind != "pull" or checked >= limit:
            continue
        checked += 1
        data = lookup(link.repo, int(link.number))
        if not data:
            link.note = "could not fetch (private, deleted, or rate limited)"
            continue
        link.verified = True
        link.author = (data.get("user") or {}).get("login")
        link.state = "merged" if data.get("merged_at") else str(data.get("state") or "unknown")
        if github_user and link.author and link.author.lower() != github_user.lower():
            link.note = f"authored by @{link.author}, not @{github_user}"
    return links


def _claims_merged(text: str, link: LinkEvidence) -> bool:
    """Whether the sentence or list item that holds the link calls it merged."""
    for line in text.splitlines():
        if link.url not in line:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line):
            if link.url in sentence and re.search(r"\bmerged\b", sentence, re.I):
                return True
    return False


def check_proposal(
    text: str,
    *,
    github_user: str | None = None,
    lookup: PullLookup | None = None,
    ideas_text: str | None = None,
    mr_lookup: MergeRequestLookup | None = None,
) -> dict[str, Any]:
    """Run every check and return findings plus the evidence behind them."""
    findings: list[Finding] = []
    sections = detect_sections(text)
    words = word_count(text)

    leftovers = placeholders(text)
    if leftovers:
        findings.append(
            Finding(
                "placeholders",
                "fail",
                f"{len(leftovers)} template placeholder(s) left in",
                ", ".join(leftovers[:5])
                + f". Google's spam guidance lists leftover placeholders first ({SPAM_GUIDANCE_URL}).",
            )
        )
    else:
        findings.append(Finding("placeholders", "pass", "No template placeholders left", ""))

    if ideas_text:
        share = mirrored_fraction(text, ideas_text)
        if share >= 0.15:
            findings.append(
                Finding(
                    "mirrors_ideas_page",
                    "fail",
                    f"{share:.0%} of the text is copied from the ideas page",
                    "Orgs reject proposals that restate their own idea; explain your approach, "
                    f"what you investigated, and your plan instead ({SPAM_GUIDANCE_URL}).",
                )
            )
        elif share >= 0.05:
            findings.append(
                Finding(
                    "mirrors_ideas_page",
                    "warn",
                    f"{share:.0%} of the text repeats the ideas page",
                    "Quote the idea briefly, then spend the words on your own analysis.",
                )
            )
        else:
            findings.append(Finding("mirrors_ideas_page", "pass", "Written in your own words", ""))

    for section in REQUIRED_SECTIONS:
        heading = sections[section]
        name = SECTION_NAMES.get(section, section)
        if heading:
            findings.append(Finding(section, "pass", f"Section found: {name}", heading))
        else:
            findings.append(
                Finding(
                    section,
                    "fail",
                    f"Section missing: {name}",
                    f"Add a heading such as '{SECTION_KEYWORDS[section][0].title()}', or use the "
                    f"name your organization's template gives it. {_REQUIRED_WHY[section]} "
                    f"({PROPOSAL_GUIDE_URL})",
                )
            )
    if not sections["availability"]:
        mention = _AVAILABILITY_RE.search(text)
        if mention:
            sections["availability"] = f"mentioned in the text ('{mention.group(0)}')"
    for section in RECOMMENDED_SECTIONS:
        heading = sections[section]
        if heading:
            findings.append(Finding(section, "pass", f"Section found: {section}", heading))
        else:
            findings.append(
                Finding(
                    section,
                    "warn",
                    f"Section missing: {section}",
                    f"{_RECOMMENDED_WHY[section]} Leave it out if your organization's "
                    "template has no such section.",
                )
            )
    if sections["ai_statement"]:
        findings.append(
            Finding("ai_statement", "pass", "States how AI was used", sections["ai_statement"])
        )
    else:
        findings.append(
            Finding(
                "ai_statement",
                "warn",
                "No statement about AI use",
                "Check the org's AI policy before you submit. Some allow no AI use at all, even "
                "in proposals; if yours allows it and its template asks, say how you used it.",
            )
        )

    links = github_links(text)
    if lookup is not None:
        verify_links(links, lookup=lookup, github_user=github_user)
    elsewhere = other_host_links(text)
    if mr_lookup is not None:
        verify_merge_requests(elsewhere, lookup=mr_lookup, github_user=github_user)
    links += elsewhere
    pulls = [link for link in links if link.kind in {"pull", "merge_request"}]
    merged = [link for link in pulls if link.state == "merged"]
    foreign = [link for link in pulls if link.note.startswith("authored by")]
    if not links:
        findings.append(
            Finding(
                "links",
                "fail",
                "No links to your contributions",
                "Link every PR, issue, or discussion you took part in for this org; "
                "prior interaction is the strongest acceptance signal.",
            )
        )
    elif not pulls:
        findings.append(
            Finding(
                "links",
                "warn",
                f"{len(links)} link(s) but no pull or merge requests",
                "A merged or reviewed PR shows you can work in the codebase; link one if you have it.",
            )
        )
    else:
        detail = f"{len(pulls)} PR or MR link(s)"
        if lookup is not None or mr_lookup is not None:
            detail += f", {len(merged)} merged"
        findings.append(Finding("links", "pass", "Links to pull or merge requests", detail))
    overclaimed = [
        link for link in pulls if link.state in {"open", "closed"} and _claims_merged(text, link)
    ]
    if overclaimed:
        findings.append(
            Finding(
                "link_claims",
                "fail",
                f"{len(overclaimed)} PR(s) described as merged are not merged",
                "; ".join(f"{link.url} is {link.state}" for link in overclaimed[:3])
                + ". Reviewers open every link; describe each PR as it is.",
            )
        )
    if foreign:
        findings.append(
            Finding(
                "link_authors",
                "fail",
                f"{len(foreign)} linked PR(s) or MR(s) were authored by someone else",
                "; ".join(f"{link.url} ({link.note})" for link in foreign[:3]),
            )
        )

    entries = timeline_entries(text)
    if entries >= 8:
        findings.append(
            Finding("timeline_detail", "pass", f"Week-by-week plan ({entries} entries)", "")
        )
    elif entries >= 3:
        findings.append(
            Finding(
                "timeline_detail",
                "warn",
                f"Timeline has only {entries} dated entries",
                "Mentors expect a week-by-week plan over the whole coding period, with buffer weeks.",
            )
        )
    else:
        findings.append(
            Finding(
                "timeline_detail",
                "fail",
                "No week-by-week timeline",
                "Add 'Week 1', 'Week 2', ... with concrete deliverables and at least one buffer week.",
            )
        )
    if re.search(r"\b(buffer|slack|contingency|catch-up|catch up)\b", text, re.IGNORECASE):
        findings.append(Finding("buffer", "pass", "Timeline mentions buffer time", ""))
    else:
        findings.append(
            Finding(
                "buffer",
                "warn",
                "No buffer time in the timeline",
                "Reviews and surprises take time; reserve some.",
            )
        )

    concrete = concrete_references(text)
    if concrete >= 6:
        findings.append(Finding("specificity", "pass", f"{concrete} concrete code references", ""))
    elif concrete >= 2:
        findings.append(
            Finding(
                "specificity",
                "warn",
                f"Only {concrete} concrete references to code, files, or issues",
                "Name the modules, functions, and issues you will touch; it proves you read the code.",
            )
        )
    else:
        findings.append(
            Finding(
                "specificity",
                "fail",
                "No concrete references to code, files, or issues",
                "Point at real files, functions, and issue numbers in the org's repository.",
            )
        )

    phrases = generic_phrases(text) + [b.rstrip("i") for b in buzzwords(text)]
    if phrases:
        findings.append(
            Finding(
                "generic_phrasing",
                "warn" if len(phrases) < 4 else "fail",
                f"{len(phrases)} generic phrase(s) or buzzword(s) that read as AI-written",
                ", ".join(f"'{p}'" for p in phrases[:6])
                + ". Replace with specifics about this project and your own experience "
                f"({SPAM_GUIDANCE_URL}).",
            )
        )
    else:
        findings.append(Finding("generic_phrasing", "pass", "No generic filler phrases", ""))

    if words < 500:
        findings.append(
            Finding(
                "length",
                "warn",
                f"Short draft ({words} words)",
                "There is no official length, but a timeline, deliverables, and links to "
                "your work rarely fit in under 500 words. Follow the organization's template.",
            )
        )
    elif words > 6000:
        findings.append(
            Finding(
                "length",
                "warn",
                f"Long draft ({words} words)",
                "Cut repetition; reviewers read dozens of these.",
            )
        )
    else:
        findings.append(Finding("length", "pass", f"{words} words", ""))

    counts = {
        status: sum(1 for f in findings if f.status == status)
        for status in ("pass", "warn", "fail")
    }
    return {
        "word_count": words,
        "sections": sections,
        "links": [asdict(link) for link in links],
        "findings": [asdict(f) for f in findings],
        "summary": counts,
        "verdict": (
            "Not ready: fix the failures first."
            if counts["fail"]
            else "Close: address the warnings, then get mentor feedback."
            if counts["warn"]
            else "Structurally complete. Now get feedback from a mentor and submit on the official site."
        ),
        "manual_checks": [
            "Does it follow the organization's own template and answer every required question?",
            "Could you explain every sentence and line of code without notes?",
            "Did a mentor or community member see a draft before the deadline?",
            "Is the submission on summerofcode.withgoogle.com, not only in a shared document?",
        ],
    }
