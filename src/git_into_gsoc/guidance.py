"""Evidence-backed educational guidance and anti-spam principles."""

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
        why="Canonical program portal for orgs, proposals, and announcements",
    ),
    OfficialSource(
        title="GSoC resources",
        url=OFFICIAL_RESOURCES,
        why="Official guides, FAQ, timeline, and contact points",
    ),
    OfficialSource(
        title="Contributor / student guide",
        url=OFFICIAL_CONTRIBUTOR_GUIDE,
        why="Proposal advice and community interaction expectations",
    ),
    OfficialSource(
        title="AI tooling guidance",
        url=OFFICIAL_AI_GUIDANCE,
        why="Org-specific AI policies; validate all AI output; never submit blind LLM work",
    ),
    OfficialSource(
        title="Spam / low-quality proposal guidance",
        url=OFFICIAL_SPAM_GUIDANCE,
        why="How orgs filter AI-generated and low-effort proposals",
    ),
]

ANTI_SPAM_RULES: list[str] = [
    "Never fabricate organizations, issues, mentors, or deadlines.",
    "Never mass-message mentors or open drive-by PRs without reading CONTRIBUTING.md.",
    "Do not submit AI-written proposals unless the org explicitly allows it — many auto-reject them.",
    "You must understand and be able to explain every line you submit.",
    "Prefer meaningful fixes/tests/docs over trivial typo spam.",
    "Interact in the org's preferred public channels before proposing.",
    "Cite evidence (issue URLs, PR links, docs) for every recommendation.",
    "If data is missing or uncertain, say so — do not guess.",
]

PHASE_GUIDES: dict[JourneyPhase, dict[str, object]] = {
    JourneyPhase.LEARN: {
        "goal": "Understand GSoC eligibility, timeline, and contributor expectations",
        "actions": [
            "Read the official GSoC home and FAQ",
            "Read AI tooling guidance and your target org's AI policy",
            "Write a short self-profile: languages, interests, weekly hours, timezone",
        ],
        "success": "You can explain GSoC in your own words and know your constraints",
    },
    JourneyPhase.DISCOVER: {
        "goal": "Find mentoring organizations that match your skills and values",
        "actions": [
            "Search orgs by technology/topic using archive data",
            "Shortlist 3-5 orgs with multi-year continuity when possible",
            "Open each org's ideas page and communication channels",
        ],
        "success": "A shortlist with evidence for why each org fits you",
    },
    JourneyPhase.EVALUATE: {
        "goal": "Verify repos are healthy and welcoming before investing weeks",
        "actions": [
            "Run repo health checks (activity, merge rate, CONTRIBUTING, CI)",
            "Confirm license and beginner pathways",
            "Drop archived, hostile, or inactive projects early",
        ],
        "success": "1-2 repos worth a serious contribution attempt",
    },
    JourneyPhase.FIND_ISSUES: {
        "goal": "Find beginner-friendly issues that are actually available",
        "actions": [
            "Search good-first-issue / help-wanted with availability checks",
            "Prefer well-specified bugs/docs/tests over vague epics",
            "Comment to confirm only after reading the issue and code pointers",
        ],
        "success": "One issue you can explain and reproduce",
    },
    JourneyPhase.CONTRIBUTE: {
        "goal": "Ship a high-quality first contribution maintainers want to merge",
        "actions": [
            "Set up the dev environment from README/CI, not guesses",
            "Implement the smallest correct change with tests when appropriate",
            "Write a clear PR that links the issue and explains tradeoffs",
        ],
        "success": "Merged or substantively reviewed PR you can defend",
    },
    JourneyPhase.COMMUNITY: {
        "goal": "Become a recognizable, helpful community member",
        "actions": [
            "Join the org's chat/mailing list and introduce yourself briefly",
            "Answer questions, triage, or review when ready",
            "Keep communication public and respectful",
        ],
        "success": "Mentors recognize your name from useful interactions",
    },
    JourneyPhase.PROPOSAL: {
        "goal": "Draft an original, org-aligned proposal with a realistic timeline",
        "actions": [
            "Use the org's template and required prerequisites",
            "Ground the proposal in prior contributions and discussions",
            "Get feedback early; revise; never paste generic LLM essays",
        ],
        "success": "Proposal you could implement even if AI tools disappeared",
    },
    JourneyPhase.TRACK: {
        "goal": "Track progress honestly through bonding and coding periods",
        "actions": [
            "Keep a weekly log of goals, blockers, and links",
            "Communicate slips early with revised scope",
            "Document deliverables for evaluations",
        ],
        "success": "No surprises for your mentor at evaluation time",
    },
}


def proposal_checklist() -> list[ProposalChecklistItem]:
    return [
        ProposalChecklistItem(
            id="org_template",
            title="Follow the organization's proposal template",
            description="Missing required sections is a common auto-reject signal.",
        ),
        ProposalChecklistItem(
            id="prior_contrib",
            title="Link prior contributions to the org",
            description="Merged PRs, issues, reviews, or docs — with URLs.",
        ),
        ProposalChecklistItem(
            id="community",
            title="Show community interaction",
            description="Public chat/mailing list presence before submission.",
        ),
        ProposalChecklistItem(
            id="scope",
            title="Clear scope, milestones, and weekly plan",
            description="Include stretch goals and what you will cut if behind.",
        ),
        ProposalChecklistItem(
            id="ai_policy",
            title="Respect the org's AI policy",
            description="State how you will use (or not use) AI, per org rules.",
        ),
        ProposalChecklistItem(
            id="original",
            title="Original authorship",
            description="Write in your voice; you must understand every claim.",
        ),
        ProposalChecklistItem(
            id="official_submit",
            title="Submit only via the official GSoC site",
            description="Do not email proposals as the formal submission.",
        ),
    ]


def journey_overview() -> dict[str, Any]:
    return {
        "anti_spam_rules": ANTI_SPAM_RULES,
        "official_sources": [s.model_dump() for s in OFFICIAL_SOURCES],
        "phases": {phase.value: PHASE_GUIDES[phase] for phase in JourneyPhase},
        "proposal_checklist": [i.model_dump() for i in proposal_checklist()],
    }
