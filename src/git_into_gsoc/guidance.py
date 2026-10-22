"""The official sources, the rules of conduct, and the phase-by-phase guidance that
the CLI, the MCP server, and the skill share."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.config import (
    OFFICIAL_AI_GUIDANCE,
    OFFICIAL_CONTRIBUTOR_GUIDE,
    OFFICIAL_GSOC_HOME,
    OFFICIAL_RESOURCES,
    OFFICIAL_SPAM_GUIDANCE,
)
from git_into_gsoc.models import JourneyPhase, OfficialSource, ProposalChecklistItem

OFFICIAL_SOURCES: list[OfficialSource] = [
    OfficialSource(
        title="Google Summer of Code home",
        url=OFFICIAL_GSOC_HOME,
        why="The official program site: organizations, proposals, and announcements",
    ),
    OfficialSource(
        title="GSoC resources",
        url=OFFICIAL_RESOURCES,
        why="Official guides, FAQ, timeline, and contacts",
    ),
    OfficialSource(
        title="Contributor / student guide",
        url=OFFICIAL_CONTRIBUTOR_GUIDE,
        why="Advice on writing a proposal and on working with a community",
    ),
    OfficialSource(
        title="AI tooling guidance",
        url=OFFICIAL_AI_GUIDANCE,
        why="What the program expects when you use AI tools; organizations add their own rules",
    ),
    OfficialSource(
        title="Spam / low-quality proposal guidance",
        url=OFFICIAL_SPAM_GUIDANCE,
        why="Why generic or low-effort proposals are rejected",
    ),
]

ANTI_SPAM_RULES: list[str] = [
    "Never fabricate organizations, issues, mentors, or deadlines.",
    "Read a project's contributing guide before opening a pull request, and never message "
    "many maintainers at once.",
    "Check the organization's AI policy before using AI. Some allow no AI tooling "
    "at all, even for writing a proposal, and the contributor stays fully "
    "responsible for the work.",
    "Understand, and be able to explain, every line you submit.",
    "Prefer a real fix, test, or documentation improvement over trivial typo changes.",
    "Talk with the organization in its public channels before you propose a project.",
    "Back every recommendation with evidence: issue links, pull request links, or docs.",
    "If something is missing or uncertain, say so. Do not guess.",
]

# The same rules, written for the person rather than for an assistant.
CONTRIBUTOR_HABITS: list[str] = [
    "Read the project's contributing guide before you open a pull request.",
    "Talk with the organization in its public channel before you propose a project. "
    "Never message many maintainers at once.",
    "Check the organization's AI policy before you apply. Some allow no AI tools at "
    "all, even for writing a proposal, and some accept no AI-generated code. You "
    "are fully responsible for everything you submit.",
    "Only submit work you understand and can explain line by line.",
    "A real fix, test, or documentation improvement counts. A typo change does not.",
]

PHASE_GUIDES: dict[JourneyPhase, dict[str, object]] = {
    JourneyPhase.LEARN: {
        "goal": "Understand how GSoC works, who can apply, and what is expected of you",
        "actions": [
            "Read the official GSoC site and FAQ",
            "Read Google's AI guidance and your target organization's AI policy",
            "Write down your languages, interests, weekly hours, and time zone",
        ],
        "success": "You can explain GSoC in your own words and know your limits",
    },
    JourneyPhase.DISCOVER: {
        "goal": "Find mentoring organizations that match your skills and interests",
        "actions": [
            "Search organizations by technology and topic",
            "Shortlist two or three organizations, preferring ones that have taken part "
            "for several years",
            "Open each organization's ideas page and community channels",
        ],
        "success": "A short list with a reason for each organization",
    },
    JourneyPhase.EVALUATE: {
        "goal": "Check that a repository is active and welcoming before you spend weeks on it",
        "actions": [
            "Run the repository health check: activity, merge rate, contributing guide, "
            "automated tests",
            "Confirm it has a license and a path for beginners",
            "Drop archived or inactive projects early",
        ],
        "success": "One or two repositories worth a serious first contribution",
    },
    JourneyPhase.ORIENT: {
        "goal": "Get your bearings in the repository before you touch code",
        "actions": [
            "Run `git-into-gsoc orient owner/repo` for the code map, entry points, test "
            "command, who merges, and the rules before a pull request",
            "Clone the project, build it, and run its test suite once before changing anything",
            "Read the contributing guide and skim three recently merged pull requests",
            "Find the files behind the feature you care about and read them end to end",
        ],
        "success": "You can say where a change would go and how you would test it",
    },
    JourneyPhase.FIND_ISSUES: {
        "goal": "Find beginner-friendly issues that are really free",
        "actions": [
            "Introduce yourself in the organization's public channel before you claim anything",
            "Search issues labeled good first issue or help wanted, and check who is already "
            "working on them",
            "Prefer clearly described bugs, documentation, and tests over vague large tasks",
            "Comment only after reading the issue and the code it points to",
        ],
        "success": "One issue you can explain and reproduce",
    },
    JourneyPhase.CONTRIBUTE: {
        "goal": "Make a first contribution that maintainers want to merge",
        "actions": [
            "Set up the project from its README and contributing guide, not from guesses",
            "Make the smallest correct change, with tests when the project uses them",
            "Write a clear pull request that links the issue and explains your choices",
        ],
        "success": "A pull request that was merged or seriously reviewed, and that you can explain",
    },
    JourneyPhase.ITERATE: {
        "goal": "See the pull request through review to a merge or a clear decision",
        "actions": [
            "Reply to every review comment within a day, even if only to say when you will fix it",
            "Push the requested changes as new commits and say what changed",
            "Ask a focused question when you are stuck instead of going quiet",
            "If the project declines the change, thank them, note what you learned, and move on",
        ],
        "success": "Reviewers know they can rely on you to finish what you start",
    },
    JourneyPhase.COMMUNITY: {
        "goal": "Become a familiar, helpful name in the community before you claim work",
        "actions": [
            "Join the organization's chat or mailing list and introduce yourself briefly",
            "Read recent conversations to learn how the project talks and decides",
            "Answer questions or review others' work when you can",
            "Keep conversations public and respectful",
        ],
        "success": "Mentors recognize your name from useful conversations",
    },
    JourneyPhase.PROPOSAL: {
        "goal": "Write an original proposal that fits the organization and has a realistic "
        "schedule",
        "actions": [
            "Use the organization's template and meet its requirements",
            "Build the proposal on your real contributions and conversations",
            "Get feedback early and revise; never paste a generic AI-written essay",
        ],
        "success": "A proposal you could carry out even without AI tools",
    },
    JourneyPhase.TRACK: {
        "goal": "Keep an honest record of progress through community bonding and coding",
        "actions": [
            "Keep a weekly log of goals, blockers, and links",
            "Say early when you are behind, and propose a smaller scope",
            "Write down what you delivered for each evaluation",
        ],
        "success": "No surprises for your mentor at evaluation time",
    },
}


def proposal_checklist() -> list[ProposalChecklistItem]:
    return [
        ProposalChecklistItem(
            id="org_template",
            title="Follow the organization's proposal template",
            description="Missing required sections is a common reason proposals are rejected.",
        ),
        ProposalChecklistItem(
            id="prior_contrib",
            title="Link prior contributions to the org",
            description="Link your merged pull requests, issues, reviews, or docs.",
        ),
        ProposalChecklistItem(
            id="community",
            title="Show community interaction",
            description="Take part in the public chat or mailing list before you submit.",
        ),
        ProposalChecklistItem(
            id="scope",
            title="Clear scope, milestones, and weekly plan",
            description="Say what you will deliver each week, what is optional, and what you will cut if you fall behind.",
        ),
        ProposalChecklistItem(
            id="ai_policy",
            title="Respect the org's AI policy",
            description="Say how you will use AI, or not, following the organization's rules.",
        ),
        ProposalChecklistItem(
            id="original",
            title="Original authorship",
            description="Write in your own voice. You must understand every claim.",
        ),
        ProposalChecklistItem(
            id="official_submit",
            title="Submit only via the official GSoC site",
            description="Emailing a proposal to a mentor is not a submission.",
        ),
    ]


def journey_overview() -> dict[str, Any]:
    return {
        "anti_spam_rules": ANTI_SPAM_RULES,
        "contributor_habits": CONTRIBUTOR_HABITS,
        "official_sources": [s.model_dump() for s in OFFICIAL_SOURCES],
        "phases": {phase.value: PHASE_GUIDES[phase] for phase in JourneyPhase},
        "proposal_checklist": [i.model_dump() for i in proposal_checklist()],
    }
