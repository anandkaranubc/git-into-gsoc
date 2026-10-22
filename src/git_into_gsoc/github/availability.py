"""Decide whether an issue is genuinely free to pick up.

Works on the issue payload plus its timeline (comments, cross-references,
assignments), so a single extra API call gives: linked PRs and their state,
who asked to work on it and when, whether a maintainer granted it, and whether
maintainers are engaged at all. During GSoC season the common failure mode is
an issue with five "can I work on this?" comments; that is surfaced as
`contested` instead of `available`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from git_into_gsoc.models import Availability, IssueAssessment, IssueClaim, LinkedPullRequest
from git_into_gsoc.text import straight_quotes

MAINTAINER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}
# Labels projects use to mark an issue as taken, with or without an assignee.
RESERVED_LABELS = {
    "assigned",
    "claimed",
    "taken",
    "in progress",
    "in-progress",
    "wip",
    "work in progress",
    "has-pr",
    "has pr",
    "pr-open",
    "pr open",
    "pr opened",
}
# The same words inside a longer label, such as "good first issue (taken)".
_RESERVED_WORD_RE = re.compile(
    r"\b(taken|claimed|in[ -]progress|wip|has[ -]pr|pr[ -]open(?:ed)?)\b", re.I
)
# Labels saying the issue is not ready for anyone to work on yet.
NOT_OPEN_LABELS = {
    "idea for discussion",
    "needs discussion",
    "discussion",
    "needs decision",
    "needs design",
    "design needed",
    "not ready",
    "on hold",
    "blocked",
}
# Projects spell these many ways ("Status: Needs-Discussion", "needs:design", "state:
# blocked"), so a label is matched after lower-casing it and turning each run of
# punctuation into one space. On 24,779 labels from the top repositories of 144 GSoC
# organizations' GitHub owners (2026-10-21), the exact names above matched 9 spellings
# and this matches 95, none of them wrongly on review. "blocker" is a priority, "design"
# a topic, and "lifecycle/frozen" only stops a bot from closing the issue.
_NOT_OPEN_LABEL_RE = re.compile(
    r"\bneeds?\s+(?:(?:further|more|community|team|a)\s+)?(?:discussion|decisions?|design)\b"
    r"|\b(?:discussion|decision|design)\s+(?:needed|required)\b"
    r"|\b(?:further|more)\s+discussion\b"
    r"|\b(?:under|in)\s+discussion\b|\bdiscussion\s+ongoing\b"
    r"|\b(?:waitfor|waiting\s+for|awaiting)\s+(?:discussion|decision)\b"
    r"|\bidea\s+for\s+discussion\b|\bnot\s+ready\b|\bon\s+hold\b|\bblocked\b"
    r"|^(?:(?:status|state|type|kind|stage|issue|todo|s|t)\s+)?discussion$"
)


def is_not_open_label(name: str) -> bool:
    """True for a label saying the issue is not ready for anyone to work on yet."""
    words = " ".join(re.sub(r"[^0-9a-z]+", " ", name.lower()).split())
    return bool(_NOT_OPEN_LABEL_RE.search(words))


# A project bot or maintainer telling claimants the issue cannot be assigned, or that
# it is the GSoC project itself, which the contributor selected for it will do
# ("reserved for gsoc, do not take over it"). "Reserved for GSoC applicants" means the
# opposite, an issue kept for people preparing to apply, so it does not count.
_NOT_OPEN_RE = re.compile(
    r"not (?:currently |yet )?(?:available|open) for (?:assignment|claims?|contributions?)"
    r"|reserved for (?:a |the )?(?:gsoc|google summer of code)\b(?!\s+(?:applicants?|aspirants?))"
    r"|reserved for the (?:selected|chosen) (?:gsoc )?(?:contributor|student|intern)",
    re.I,
)
RECENT_CLAIM_DAYS = 30
STALE_PR_DAYS = 90
CONTESTED_WINDOW_DAYS = 60
CONTESTED_MIN_CLAIMANTS = 3
STALE_DAYS = 365

_CLAIM_PATTERNS = [
    r"\bi(?:'m| am) (?:currently |now )?working on (?:this|it|the issue)\b",
    r"\bi(?:'ll| will) (?:take|work on|pick up|handle|fix) (?:this|it)\b",
    r"(?<!how )\b(?:can|could|may) i (?:please )?(?:work on|take|pick up|tackle|fix|be assigned|"
    r"get assigned)\b",
    r"\b(?:please |kindly )?(?<!un-)(?<!un)assign (?:this |it )?(?:issue )?(?:to )?me\b",
    r"\bi(?:'d| would) (?:really )?(?:like|love) to (?:work on|take|tackle|pick up|fix|contribute to) (?:this|it)\b",
    r"\b(?:i want|wanting) to work on (?:this|it)\b",
    r"\b(?:happy|glad) to (?:work on|take on|pick up|take|fix) (?:this|it)\b",
    r"\bi(?:'d| would) (?:really )?(?:like|love) to (?:pick|take) (?:this|it) (?:up|on)\b",
    r"\bclaiming (?:this|it)\b",
    r"\bi(?:'ve| have) (?:started|begun) working\b",
    r"\bis (?:this|it) (?:still )?(?:available|open) (?:to|for) (?:work|take)\b",
    # Phrasings measured on 280 real comments in GSoC organizations' beginner issues
    # (2026-10-21): the patterns above caught 62% of the claims in them.
    r"(?:(?<!we )(?<!you )(?<!they )\bwould|\bi'd|\bid|\bi)\s+(?:really\s+|also\s+)?"
    r"(?:like|love|be (?:happy|glad))\s+to\s+"
    r"(?:work|claim|take|tackle|pick|fix|resolve|solve|contribute|help|try|give it|open a pr|"
    r"implement|add|start)\b",
    r"\bi(?:'d| would) (?:like|love) to be assigned\b",
    r"(?:^|[.!?,]\s*)working on (?:this|it|a fix|the fix)\b",  # "Working on this." at a start
    r"\b(?:i(?:'m| am)|i(?:'ve| have) (?:already )?been) "
    r"(?:actively |currently |already |now |still |still actively )?"
    r"working on\b",
    r"\bassign (?:this|it|the issue|this issue|#\d+|[\w -]{1,40}? issue) to me\b",
    r"(?<!how )(?<!where )\b(?:can|could|may) i (?:please |also )?(?:try|attempt|give it|work|"
    r"handle|resolve|take|add|start)\b",
    r"(?<!how )\bshould i (?:try|attempt|give it a|take|work on|start)\b",
    r"\bi can (?:also )?(?:work on|take|fix|handle|resolve) (?:this|it)\b",
    r"\bi(?:'ll| will) (?:start working|work on|try to (?:resolve|fix|solve)|implement|"
    r"submit a pr|open a pr|raise a pr|create a pr|take (?:this|it|up))\b",
    r"\b(?:i(?:'m| am) )?(?:planning|going) to (?:work on|fix|tackle|implement|take)\b",
    r"\bi(?:'m| am|'d be| would be)?\s+(?:very |really |also |quite |still )?interested in "
    r"(?:working on|taking|fixing|solving|contributing to|helping)\b",
    r"\b(?:is|if) (?:this|it|the issue|this issue) (?:is )?(?:still )?(?:open|available) "
    r"(?:for|to)\b",
    r"\bavailable for me to (?:take|work on)\b",
    r"\b(?:take a stab at|give it a (?:go|try|shot))\b",
    r"\bstarting (?:the )?work\b|\bwill (?:be )?creat(?:e|ing) (?:a )?pr\b",
    # A second sample of 333 comments from 20 other organizations (2026-10-21).
    r"\b(?:would|i'd) (?:love|like) (?:an |the )?assignment\b",
    r"\b(?:assign|delegate|give) (?:this|it|the issue|this issue) to (?:me|us)\b",
    r"\bi(?:'m| am) planning to\b|\bi plan to\b",
    r"\b(?:i(?:'ll| will)|will) get started\b",
    # Work already begun, missed in two Java issues (2026-10-21).
    r"\bi(?:'ve| have) (?:tried|attempted) to (?:implement|fix|solve|resolve|address)\b",
    r"\bi(?:'ve| have) been looking into (?:implementing|fixing|solving|this|it)\b",
    r"\bi wanna (?:take|work|fix|try|do)\b",
    r"\bi have (?:the |a )?(?:change|changes|fix|patch|pr) ready\b",
    r"\bi(?:'m| am) (?:nearly|almost) (?:done|finished)\b",
    r"^\s*take\s*$|^\s*taking (?:this|it)\b",  # pandas-style "take" comment, or "Taking this one."
    r"\bi want to (?:work on|fix|take|tackle|solve|resolve) (?:this|it)\b",
    r"\bi(?:'ll| will) be (?:taking|working on|picking up)\b",
    r"\b(?:formally |officially )?take (?:this|the) issue\b",
    # Forms still missed in both samples, kept general (third sample measures them).
    r"(?:^|[.!?,]\s*|\bhi,?\s+)am (?:actively |currently |still )?working on\b",
    r"(?<!anyone )(?<!someone )(?<!is )(?<!are )(?<!you )(?<!if )(?<!you still )"
    r"\bworking on (?:it|a fix)\b",
    r"\b(?:should|shall|can|could|may) i (?:directly |go ahead and )?(?:submit|open|raise|make|create|send)"
    r" (?:a |the |my )?(?:pr|pull request)\b",
    r"\bwould you (?:mind|prefer|like) (?:if|that|it if) i\b",
    r"\b(?:i(?:'ll| will)|will) (?:be )?(?:raising|opening|submitting|sending|creating) (?:a |the |my )?"
    r"(?:pr|pull request)\b",
    r"\bi(?:'ll| will) have a look (?:into|at) (?:this|it)\b",
    r"\btrying to (?:resolve|fix|solve) (?:this|it)\b",
    r"\bi can fix (?:this|it|both|them)\b",
    # A third sample (387 comments, 20 more organizations) found these missing: Checkstyle
    # contributors split big issues with "I am on it" and "I'll cover <part>".
    r"\bi(?:'m| am| m)? on (?:it|this)\b",
    r"\bi(?:'ll| will) (?:cover|take on|take care of)\b",
    r"\bi(?:'ll| will) take (?:the|this|it|these|those|that|both|all|over)\b",
    r"\bi(?:'m| am) (?:covering|taking over|taking (?:this|it))\b|\bi(?:'ve| have) taken\b",
    r"\bcan (?:this|it) (?:issue )?be assigned to me\b",
    r"\b(?:could|can|may) i (?:claim|look (?:on|at|into))\b",
    r"\bi (?:really )?want to (?:work on|fix|take|tackle|solve|resolve|contribute to)\b",
    r"\b(?:i'?d be|i(?:'m| am)?) glad to (?:help with|help on|work|take|fix|submit a fix|contribute)\b",
    r"\bi was (?:just )?working on (?:this|it)\b",
    # Still missed in the first three samples (2026-10-22); a fourth sample from 17 new
    # organizations, labelled before these were written, measured them.
    r"\byes,? i(?:'m| am) working\b|\bi work on (?:this|it)\b",
    r"\b(?:happy|glad) to help (?:with |on )?(?:this|it)\b",
    r"(?:^|[.!?]\s*|\bhi,?\s+)(?:very |really |also )?interested in "
    r"(?:working on|taking|fixing|solving|contributing to|helping)\b",
    r"\bi(?:'ll| will) take\s*(?:[.!,]|$)",  # "I'll take." but not "I'll take a look"
    r"\b(?:like|love) (?:to )?on (?:this|it)\b",  # "would love to on this", a word dropped
    r"\b(?:update you|keep you posted|report back) on my progress\b|\bupdate on my progress\b",
    r"\bi(?:'ll| will) (?:really )?(?:love|like) to (?:work|fix|take|contribute|help|try)\b",
    r"\bi(?:'m| am) (?:currently |now )?(?:porting|implementing|migrating|refactoring)\b",
    r"\bi(?:'ll| will) working on\b|\bi(?:'m| am) workin'? on\b",  # common slips
    r"\b(?:also|i(?:'m| am)) taking (?:the|these|those|over|care of)\b",  # not "Taking the example"
    r"\bplease assigned? (?:it |this |the issue )?to me\b",
    r"\bi(?:'ll| will) proceed with\b|\bi tried to work on (?:this|it)\b",
    r"\bi(?:'m| am) willing to (?:contribute|work|help|take|fix)\b",
    r"\bwould it be (?:ok|okay|fine|alright) if i\b",
    r"\b(?:would|i'd)\s+(?:like|love|be (?:happy|glad))\s+to\s+(?:raise|explore)\b",
    # Forms seen in a fourth sample (17 new organizations), added after it measured the
    # rules above at 82% recall: so its figures after this change are not held out.
    # Only with the writer as the subject: not "so someone else can pick it up".
    r"(?:^|[.!?]\s*|\bi(?:'m| am|'ll| will)?\s+|\b(?:happy|glad|like|love) to\s+)"
    r"pick(?:ing|ed)? (?:this|it|this issue|the issue) up\b",
    r"\bi(?:'m| am) starting (?:on|with) (?:this|it)\b|(?:^|[.!?]\s*)will start working\b",
    r"\bassign (?:this|the) task to me\b|\binterested[,.!]?\s+(?:please )?assign\b",
    r"\b(?:would|i'd) (?:like|love) work on\b|\binterested (?:to|on) work (?:on|in)\b",
    r"\bgiving (?:this|it) a (?:go|try|shot)\b|\btry my hand\b",
    r"\bi(?:'ll| will) (?:raise|open|submit|create|send) (?:a|the|my) (?:pr|pull request)\b",
    r"\bi(?:'ll| will) (?:really )?(?:love|like) to submit\b",
    r"(?<!anyone )(?<!you )\bstill on (?:this|it)\b",
    r"^\s*(?:in progress|pr soon)\b",
    r"\bdo you want me to (?:work on|take|fix)\b",
    r"\b(?:we|i) (?:could|can) work (?:on (?:this|it) )?together\b",  # a second claimant
    # A fifth sample (568 comments, 21 organizations never sampled, labelled blind)
    # measured 78% recall held out; these come from its tuning half only, split by
    # issue thread, so the other half still measures them fairly.
    r"\bi(?:'ll| will| shall) (?:work on|take|handle|fix) (?:this|it)\b",
    r"\b(?:can|could|may) i (?:please )?(?:address|do) (?:this|it)\b",
    r"\b(?:please )?let me (?:work on|take|fix|handle|tackle|try)\b",
    r"\bplease assign (?:it|this)\s*(?:[.!]|$)|\badd me as (?:a |an )?(?:co-?)?assignee\b",
    r"\bi can (?:also )?(?:take|pick) up (?:this|it)\b",
    r"\bi(?:'ll| will) (?:raise|open|submit|create|send) (?:a |the |my )?(?:pr|pull request)\b",
    r"\bi(?:'m| am) (?:raising|opening|submitting|creating) (?:a |the |my )?(?:pr|pull request)\b",
    r"\bi (?:have )?(?:started|began) (?:implementing|working|looking into (?:this|it)|on (?:this|it))\b",
    r"\btaking (?:this|it) up\b|\bself[- ]?assigned\b",
    # Work already done on it: "I have made minimal changes to fix this".
    r"\bi(?:'ve| have) (?:just )?(?:implemented (?:it|this|the)|fixed (?:it|this)|"
    r"made (?:the |some |minimal |a few )?changes to (?:fix|resolve|address|solve))\b",
    r"\b(?:my|the) (?:work|changes|fix) (?:is|are) ready\b",
    r"\b(?:i want to|can (?:we|i)|could (?:we|i)|we can) (?:both )?collab(?:orate)?\b",
    r"\bi(?:'ll| will) (?:take a look|look) into (?:this|it)\b",
    r"^\s*(?:hi,?\s*)?i(?:'m| am) interested[.!]?\s*$",
    # bot commands used by Kubernetes, pandas, Zulip, Rust, Beam and others
    r"^\s*/(?:assign(?:-me)?|take|claim|attempt)\s*$",
    r"^\s*\.take(?:-issue)?\s*$",
    r"^\s*@[\w-]+\s+(?:claim|assign)\s*$",  # "@zulipbot claim", "@openwisp-companion assign"
    # Git Bash on Windows turns a typed /assign into a path.
    r"^\s*[a-z]:/program files/git/(?:assign|take|claim)\s*$",
]
_RELEASE_PATTERNS = [
    r"^\s*/(?:unassign(?:-me)?|release|unclaim)\s*$",
    r"^\s*\.(?:release|unassign)\s*$",
    r"^\s*@\w+bot\s+(?:abandon|unclaim|release)\b",
    r"\b(?:i(?:'m| am) )?no longer (?:working on|able to work on|interested in) (?:this|it)\b",
    r"\b(?:please )?un-?assign me\b",
    r"\bfeel free to (?:take|pick) (?:this|it) (?:over|up)\b",
    r"\bhas been (?:automatically )?unassigned\b",
    r"\bunassigned (?:due to|because of|for) inactivity\b",
]
# Giving back one's own claim. A report about someone else ("the assignee is no
# longer working on this, so can I take it?") must not cancel the writer's claim.
_OWN_RELEASE_PATTERNS = [
    r"^\s*/(?:unassign(?:-me)?|release|unclaim)\s*$",
    r"^\s*\.(?:release|unassign)\s*$",
    r"\bi(?:'m| am| can)? no longer (?:working on|able to|interested in)\b",
    r"\b(?:please )?un-?assign me\b",
    r"\bi(?:'m| am) (?:not |un)able to (?:continue|work on|finish|complete|set up)\b",
]
_GRANT_PATTERNS = [
    r"\bassigned\b",
    r"\bgo ahead\b",
    r"\bgo for it\b",
    r"\bfeel free\b",
    r"\ball yours\b",
    r"\bsure,? (?:go|you can|please)\b",
    r"\b(?:this|that|your plan|the plan|your approach) (?:sounds|looks) (?:good|great|fine)\b",
]
# A comment pointing at a pull request: "covered by #1293", "PR #12", or a PR link.
_PR_MENTION_RE = re.compile(
    r"\b(?:PR|pull request)\s*#(\d+)"
    r"|\b(?:covered|fixed|addressed|resolved|handled|implemented|solved|done|tackled)"
    r"\s+(?:by|in|with|via)\s+#(\d+)"
    r"|https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)",
    re.IGNORECASE,
)
MAX_PR_LOOKUPS = 3

_PULL_URL_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", re.IGNORECASE)

# Issues moved from Jira keep their old key, and pull requests often name only that key
# ("Fixes JENKINS-43785"), so GitHub never links them. Each importer leaves a marker; a
# key merely mentioned in an issue is not enough. On 2026-10-22, 20 of the 27 open
# Jenkins "good first issue" issues imported from Jira had a pull request naming the key.
_JIRA_IMPORT_RES = (
    re.compile(r"\[jira_issue_key=([A-Z][A-Z0-9]+-\d+)\]"),  # Jenkins' importer
    re.compile(r'imported from: <a href="[^"]*/jira/browse/([A-Z][A-Z0-9]+-\d+)"'),  # Apache's
)


def imported_jira_key(body: str | None) -> str | None:
    """The Jira key of an issue imported from Jira, such as 'JENKINS-43785'."""
    for pattern in _JIRA_IMPORT_RES:
        found = pattern.search(body or "")
        if found:
            return found.group(1)
    return None


# (repository, number) -> the pull request, or None
PullLookup = Callable[[str, int], dict[str, Any] | None]
_CLAIM_RE = re.compile("|".join(_CLAIM_PATTERNS), re.IGNORECASE | re.MULTILINE)
_GRANT_RE = re.compile("|".join(_GRANT_PATTERNS), re.IGNORECASE)
_RELEASE_RE = re.compile("|".join(_RELEASE_PATTERNS), re.IGNORECASE | re.MULTILINE)
_OWN_RELEASE_RE = re.compile("|".join(_OWN_RELEASE_PATTERNS), re.IGNORECASE | re.MULTILINE)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _login(obj: dict[str, Any] | None) -> str | None:
    return (obj or {}).get("login")


def _is_bot(user: dict[str, Any] | None) -> bool:
    login = _login(user) or ""
    return (user or {}).get("type") == "Bot" or login.endswith("[bot]")


_QUOTED_LINE = re.compile(r"^\s*>.*$", re.MULTILINE)


def _own_words(text: str) -> str:
    """The comment without lines quoted from someone else ("> I would like to...")."""
    return _QUOTED_LINE.sub("", straight_quotes(text))


def is_claim(text: str) -> bool:
    # "I'd like to take this one", typed with a curly apostrophe, went unseen on
    # OWASP/SecurityShepherd#411.
    return bool(_CLAIM_RE.search(_own_words(text)))


def is_grant(text: str) -> bool:
    return bool(_GRANT_RE.search(straight_quotes(text)))


def is_own_release(text: str) -> bool:
    """The writer gives back their own claim (not a report about someone else's)."""
    return bool(_OWN_RELEASE_RE.search(_own_words(text)))


def is_release(text: str) -> bool:
    """A comment that gives an issue back: a bot command, a withdrawal, or an auto-unassign."""
    return bool(_RELEASE_RE.search(straight_quotes(text)))


def _mentioned_pulls(body: str, repo: str) -> list[tuple[str, int]]:
    """Pull requests a comment points at, as (repository, number).

    A link can name another repository: work on a tool's issue sometimes lands in
    the repository that uses it.
    """
    found: list[tuple[str, int]] = []
    for match in _PR_MENTION_RE.finditer(body):
        short, covered, other_repo, linked_number = match.groups()
        found.append((other_repo or repo, int(short or covered or linked_number)))
    return found


def pull_ref(number: int | None, url: str | None, repo: str) -> str:
    """'#12' for a pull request of this repository, 'owner/name#12' for another one."""
    if not number:
        return ""
    match = _PULL_URL_RE.search(url or "")
    where = match.group(1) if match else repo
    same = not repo or where.lower() == repo.lower()
    return f"#{number}" if same else f"{where}#{number}"


def _pull_ref(pr: LinkedPullRequest, repo: str) -> str:
    return pull_ref(pr.number, pr.url, repo)


def _pull_key(pr: LinkedPullRequest, repo: str) -> tuple[str, int | None]:
    match = _PULL_URL_RE.search(pr.url or "")
    return ((match.group(1) if match else repo).lower(), pr.number)


def _source_repo(source: dict[str, Any]) -> str:
    """owner/name of the repository a cross-referencing issue or PR lives in."""
    named = str((source.get("repository") or {}).get("full_name") or "")
    return named or _issue_repo(source)


def _related_repo(source: str, repo: str) -> bool:
    """A pull request that can fix an issue: in its repository, a sibling repository of
    the same owner, or a fork (same name). A pull request in an unrelated project that
    only mentions the issue is not one: this tool's own repository once named a
    CircuitVerse issue in a merged pull request, and `issue` then said a merged pull
    request "may already" have fixed it.
    """
    if not source or not repo:
        return True
    s_owner, _, s_name = source.lower().partition("/")
    r_owner, _, r_name = repo.lower().partition("/")
    return s_owner == r_owner or s_name == r_name


def _issue_repo(issue: dict[str, Any]) -> str:
    url = str(issue.get("html_url") or "")
    parts = url.split("github.com/", 1)[-1].split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


_FIX_VERB = r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b"


def says_it_fixes(text: str, repo: str, number: object, *, pr_repo: str = "") -> bool:
    """True when a pull request's text says it fixes this issue.

    GitHub closes an issue only for "Fixes #671" merged into the default branch. mofa's
    "- Fixes issue #671" and mixxx's "Fixes first-run experience for #14905's underlying
    UX issue" (merged into a release branch) left both issues open, and `recommend`
    showed them as free starter issues.
    """
    if not number or not text:
        return False
    # A bare "#671" means the pull request's own repository's issue: it counts only for
    # a pull request in the issue's repository. One from a sibling repository must name
    # "owner/repo#671" or link the issue.
    own = not pr_repo or pr_repo.lower() == repo.lower()
    forms = [rf"(?<![\w/.-])#{number}(?!\d)"] if own else []
    if repo:
        forms += [rf"{re.escape(repo)}#{number}(?!\d)", rf"{re.escape(repo)}/issues/{number}(?!\d)"]
    if not forms:
        return False
    ref = "|".join(forms)
    # Up to 80 characters of the same sentence: a full stop ends it, a dot in a link
    # ("github.com/...") does not.
    return bool(re.search(rf"{_FIX_VERB}(?:[^.\n]|\.(?=\S)){{0,80}}?(?:{ref})", text, re.I))


def assess_issue(
    issue: dict[str, Any],
    timeline: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    pull_lookup: PullLookup | None = None,
) -> IssueAssessment:
    """Classify one issue from its payload and timeline.

    `pull_lookup(repository, number)` returns that pull request, or None. With it, a
    comment such as "this is covered by #1293" counts when that pull request is open,
    even though the pull request itself never links the issue.
    """
    now = now or datetime.now(UTC)
    caveats: list[str] = []
    claims: dict[str, IssueClaim] = {}
    linked: dict[str, LinkedPullRequest] = {}
    mentioned: list[tuple[str, int]] = []
    earlier: set[str] = set()  # keys in `linked` of pull requests merged before the issue
    opened = _dt(issue.get("created_at"))
    repo = _issue_repo(issue)
    maintainer_engaged = False
    last_activity = _dt(issue.get("updated_at"))

    not_open: str | None = None
    for event in timeline:
        kind = event.get("event")
        at = _dt(event.get("created_at") or event.get("updated_at"))
        if kind == "commented":
            user = event.get("user") or event.get("actor")
            body = str(event.get("body") or "")
            said = _NOT_OPEN_RE.search(body)
            if said and (
                _is_bot(user) or str(event.get("author_association") or "") in MAINTAINER_ROLES
            ):
                not_open = f"The project said it is {said.group(0)}"
                if said.group(0).lower().startswith("reserved"):
                    not_open += ": the contributor chosen for that GSoC project does this work"
            if _is_bot(user):
                if is_release(body):
                    _release(claims, body, caveats, who=None)
                continue
            role = str(event.get("author_association") or "")
            login = _login(user)
            if is_release(body) and login:
                _release(claims, body, caveats, who=login)
            mentioned += _mentioned_pulls(body, repo)
            if role in MAINTAINER_ROLES:
                maintainer_engaged = True
                if is_grant(body):
                    _grant(claims, body)
                # "@x are you still working on this?" keeps x's claim alive.
                if at is not None:
                    for name in set(re.findall(r"@([A-Za-z0-9-]+)", body)) & set(claims):
                        _touch(claims[name], at, now)
            elif is_claim(body) and not is_own_release(body) and at is not None and login:
                if login in claims:
                    _touch(claims[login], at, now)
                else:
                    claims[login] = IssueClaim(login=login, at=at, days_ago=(now - at).days)
            elif login in claims and not is_release(body) and at is not None:
                _touch(claims[login], at, now)  # the claimant is still talking about it
        elif kind == "unassigned":
            login = _login(event.get("assignee"))
            if login and login in claims:
                del claims[login]
                caveats.append(f"@{login} was unassigned later; the issue is open again")
        elif kind == "cross-referenced":
            source = (event.get("source") or {}).get("issue") or {}
            where = _source_repo(source)
            if "pull_request" in source and not _related_repo(where, repo):
                # Shown, so nothing is hidden, but it neither takes nor fixes the issue.
                caveats.append(
                    f"A pull request in another project, {where}#{source.get('number')}, "
                    "mentions this issue; it does not change its status here"
                )
            elif "pull_request" in source:
                merged_at = _dt((source.get("pull_request") or {}).get("merged_at"))
                merged = merged_at is not None
                number = source.get("number")
                key = str(number or source.get("html_url") or len(linked))
                if merged_at and opened and merged_at < opened:
                    earlier.add(key)
                touched = _dt(source.get("updated_at"))
                text = f"{source.get('title') or ''}\n{source.get('body') or ''}"
                linked[key] = LinkedPullRequest(
                    number=int(number) if number else None,
                    url=source.get("html_url"),
                    state="merged" if merged else str(source.get("state") or "unknown"),
                    author=_login(source.get("user")),
                    draft=bool(source.get("draft")),
                    idle_days=(now - touched).days if touched else None,
                    # Merged after the issue opened, like the decision below requires.
                    fixes=merged
                    and not (merged_at and opened and merged_at < opened)
                    and says_it_fixes(text, repo, issue.get("number"), pr_repo=where),
                )
        elif kind == "connected":
            caveats.append(
                "A PR may be linked through the Development sidebar; check before starting"
            )
        if at and (last_activity is None or at > last_activity):
            last_activity = at

    known = {_pull_key(p, repo) for p in linked.values()} | {(repo.lower(), issue.get("number"))}
    wanted = [(r, n) for r, n in dict.fromkeys(mentioned) if (r.lower(), n) not in known]
    for where, number in wanted[:MAX_PR_LOOKUPS]:
        pull = pull_lookup(where, number) if pull_lookup else None
        if not pull:
            continue  # not a pull request, or it could not be read
        merged_at = _dt(pull.get("merged_at"))
        state = "merged" if merged_at else str(pull.get("state") or "unknown")
        if state == "closed":
            continue
        touched = _dt(pull.get("updated_at"))
        if merged_at and opened and merged_at < opened:
            earlier.add(f"comment-{where}-{number}")
        text = f"{pull.get('title') or ''}\n{pull.get('body') or ''}"
        linked[f"comment-{where}-{number}"] = LinkedPullRequest(
            number=number,
            url=pull.get("html_url") or f"https://github.com/{where}/pull/{number}",
            state=state,
            author=_login(pull.get("user")),
            draft=bool(pull.get("draft")),
            idle_days=(now - touched).days if touched else None,
            via_comment=True,
            fixes=state == "merged"
            and not (merged_at and opened and merged_at < opened)
            and says_it_fixes(text, repo, issue.get("number"), pr_repo=where),
        )

    assignees = [a for a in (_login(x) for x in issue.get("assignees") or []) if a]
    if not assignees and issue.get("assignee"):
        assignees = [a for a in [_login(issue.get("assignee"))] if a]
    prs = sorted(linked.values(), key=lambda p: p.number or 0)
    claim_list = sorted(claims.values(), key=lambda c: c.at, reverse=True)
    activity_days = (now - last_activity).days if last_activity else None

    # A pull request merged before the issue was opened cannot be its fix: the issue is
    # often a follow-up to it ("Follow-up on PR #1695", opened 26 minutes after the merge).
    before = {id(linked[k]) for k in earlier if k in linked}
    merged_prs = [p for p in prs if p.state == "merged" and id(p) not in before]
    if any(not p.via_comment and not p.fixes for p in merged_prs):
        caveats.append("A merged PR references this issue; it may already be partly fixed")
    # A comment can link a merged pull request as the fix or as an example to copy.
    for p in [p for p in merged_prs if p.via_comment][:2]:
        caveats.append(
            f"A comment links merged PR {_pull_ref(p, repo)}; read it first, it may already "
            "fix this or show how to fix it"
        )
    abandoned = [p for p in prs if p.state == "closed"]
    if abandoned and not any(p.state in {"open", "merged"} for p in prs):
        refs = ", ".join(_pull_ref(p, repo) for p in abandoned[:3] if p.number) or "an earlier PR"
        caveats.append(
            f"{refs} tried this and was closed without merging; read its review comments "
            "first, they show what the maintainers expect"
        )

    def result(status: Availability, reason: str) -> IssueAssessment:
        return IssueAssessment(
            availability=status,
            reason=reason,
            claims=claim_list,
            linked_prs=prs,
            assignees=assignees,
            maintainer_engaged=maintainer_engaged,
            last_activity_days=activity_days,
            caveats=list(dict.fromkeys(caveats)),
        )

    if issue.get("state") and issue.get("state") != "open":
        return result(Availability.CLOSED, "Issue is closed")
    if assignees:
        return result(Availability.ASSIGNED, "Assigned to " + ", ".join(f"@{a}" for a in assignees))

    open_prs = [p for p in prs if p.state == "open"]
    if open_prs:
        pr = open_prs[0]
        ref = _pull_ref(pr, repo)
        who = f" by @{pr.author}" if pr.author else ""
        draft = " (draft)" if pr.draft else ""
        reason = (
            f"A comment says open PR {ref}{who}{draft} covers it"
            if pr.via_comment
            else f"Open PR {ref}{who}{draft} references it"
        ).replace("  ", " ")
        if pr.idle_days is not None and pr.idle_days >= STALE_PR_DAYS:
            # Still someone else's work, but a quiet one: say how to ask, as
            # is-it-claimed does, instead of implying the issue is out of reach.
            reason += f"; it has been idle for {pr.idle_days} days"
            caveats.append(
                f"The open PR has had no activity for {pr.idle_days} days; ask in the issue "
                "whether its author is still working on it before you start"
            )
        return result(Availability.LIKELY_TAKEN, reason)

    # Merged and saying it fixes this, but GitHub left the issue open (no closing
    # keyword it knows, or a merge into a release branch): probably done already.
    fixed = [p for p in merged_prs if p.fixes]
    if fixed:
        return result(
            Availability.LIKELY_TAKEN,
            f"Merged PR {_pull_ref(fixed[0], repo)} says it fixes this, though the issue is "
            "still open: it is probably done. Ask in the thread whether anything is left "
            "before you start",
        )

    names = [
        str(lab.get("name") if isinstance(lab, dict) else lab) for lab in issue.get("labels") or []
    ]
    held = [name for name in names if is_not_open_label(name)]
    if held or not_open:
        reason = (
            f"Labelled '{held[0]}': the project is not taking claims on it yet"
            if held
            else str(not_open)
        )
        return result(Availability.NOT_OPEN, reason + "; pick another issue")
    reserved = [
        name
        for name in names
        if name.strip().lower() in RESERVED_LABELS or _RESERVED_WORD_RE.search(name)
    ]
    if reserved:
        return result(Availability.CLAIMED, f"Label '{reserved[0]}' marks it as taken")

    granted = [c for c in claim_list if c.granted and c.days_ago <= CONTESTED_WINDOW_DAYS]
    if granted:
        c = granted[0]
        return result(
            Availability.CLAIMED,
            f"A maintainer approved @{c.login}; the claim was last active {c.days_ago}d ago",
        )
    window = [c for c in claim_list if c.days_ago <= CONTESTED_WINDOW_DAYS]
    if len(window) >= CONTESTED_MIN_CLAIMANTS:
        return result(
            Availability.CONTESTED,
            f"{len(window)} people asked to work on this in the last {CONTESTED_WINDOW_DAYS} days",
        )
    recent = [c for c in claim_list if c.days_ago <= RECENT_CLAIM_DAYS]
    if recent:
        c = recent[0]
        return result(
            Availability.CLAIMED,
            f"@{c.login} asked to work on it; the claim was last active {c.days_ago}d ago",
        )
    if len(claim_list) >= CONTESTED_MIN_CLAIMANTS:
        # Spread over months it is not CONTESTED, but a fourth "can I work on this?"
        # is still the noise maintainers dread.
        caveats.append(
            f"{len(claim_list)} people asked to work on this, the latest "
            f"{claim_list[0].days_ago}d ago, and none opened a PR; post a concrete plan "
            "instead of another request, or pick another issue"
        )
    elif claim_list:
        c = claim_list[0]
        caveats.append(
            f"@{c.login} asked {c.days_ago}d ago with no PR; ask politely in the thread first"
        )
    if activity_days is not None and activity_days > STALE_DAYS and not maintainer_engaged:
        return result(Availability.STALE, f"No activity for {activity_days} days")
    # "Recent" said in days: a beginner read "no recent claim" right above a claim made
    # 50 days ago and could not tell which was true.
    return result(
        Availability.AVAILABLE,
        f"Open, unassigned, no open PR, and no claim in the last {RECENT_CLAIM_DAYS} days",
    )


def unverified_assessment() -> IssueAssessment:
    """Assessment to use when the issue timeline could not be fetched."""
    return IssueAssessment(
        availability=Availability.UNKNOWN,
        reason=(
            "Could not read the issue timeline; open the issue and check for claims "
            "and linked PRs yourself"
        ),
        caveats=["The timeline request failed, so claims and linked PRs were not checked"],
    )


def _release(
    claims: dict[str, IssueClaim], body: str, caveats: list[str], *, who: str | None
) -> None:
    """Drop claims a comment gives back: the author's own, or those it mentions."""
    mentioned = set(re.findall(r"@([A-Za-z0-9-]+)", body))
    targets = [login for login in claims if login in mentioned or (who and login == who)]
    if not targets and who is None and len(claims) == 1:
        targets = list(claims)
    for login in targets:
        del claims[login]
        caveats.append(f"@{login} released this issue later; it is open again")


def _touch(claim: IssueClaim, at: datetime, now: datetime) -> None:
    """Move a claim's last sign of life forward."""
    if at > claim.at:
        claim.at = at
        claim.days_ago = (now - at).days


def _grant(claims: dict[str, IssueClaim], body: str) -> None:
    mentioned = set(re.findall(r"@([A-Za-z0-9-]+)", body))
    targets = [c for login, c in claims.items() if login in mentioned]
    if not targets and claims:
        targets = [max(claims.values(), key=lambda c: c.at)]
    for claim in targets:
        claim.granted = True
