"""Shared Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from git_into_gsoc.config import DEFAULT_TARGET_YEAR


class JourneyPhase(StrEnum):
    LEARN = "learn"
    DISCOVER = "discover"
    EVALUATE = "evaluate"
    ORIENT = "orient"
    COMMUNITY = "community"
    FIND_ISSUES = "find_issues"
    CONTRIBUTE = "contribute"
    ITERATE = "iterate"
    PROPOSAL = "proposal"
    TRACK = "track"


class Availability(StrEnum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    CONTESTED = "contested"
    LIKELY_TAKEN = "likely_taken"
    ASSIGNED = "assigned"
    STALE = "stale"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class IssueClaim(BaseModel):
    login: str
    at: datetime
    days_ago: int
    granted: bool = False


class LinkedPullRequest(BaseModel):
    number: int | None = None
    url: str | None = None
    state: str = "unknown"
    author: str | None = None
    draft: bool = False
    idle_days: int | None = None


class IssueAssessment(BaseModel):
    availability: Availability
    reason: str
    claims: list[IssueClaim] = Field(default_factory=list)
    linked_prs: list[LinkedPullRequest] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    maintainer_engaged: bool = False
    last_activity_days: int | None = None
    caveats: list[str] = Field(default_factory=list)


class ContactChannel(BaseModel):
    kind: str
    value: str


class PastProject(BaseModel):
    year: int
    org: str
    title: str
    summary: str = ""
    project_url: str | None = None
    code_url: str | None = None
    score: float = 0.0


class OrgSummary(BaseModel):
    name: str
    slug: str | None = None
    description: str = ""
    url: str | None = None
    category: str | None = None
    topics: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    license: str | None = None
    years_active: list[int] = Field(default_factory=list)
    latest_year: int | None = None
    num_projects_latest: int = 0
    projects_by_year: dict[int, int] = Field(default_factory=dict)
    ideas_url: str | None = None
    guide_url: str | None = None
    source_code: str | None = None
    github_orgs: list[str] = Field(default_factory=list)
    github_repos: list[str] = Field(default_factory=list)
    channels: list[ContactChannel] = Field(default_factory=list)
    official: bool = False
    match_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    recent_projects: list[PastProject] = Field(default_factory=list)


class OrgCatalog(BaseModel):
    year: int
    source: str
    note: str
    count: int


class RepoHealth(BaseModel):
    full_name: str
    url: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    archived: bool = False
    disabled: bool = False
    pushed_at: datetime | None = None
    license: str | None = None
    topics: list[str] = Field(default_factory=list)
    has_contributing: bool = False
    has_code_of_conduct: bool = False
    has_issue_template: bool = False
    has_pr_template: bool = False
    has_ci: bool = False
    prs_sampled: int = 0
    merge_rate: float | None = None
    median_pr_hours: float | None = None
    outsider_prs_sampled: int = 0
    outsider_merge_rate: float | None = None
    outside_authors_merged: int = 0
    median_first_response_hours: float | None = None
    first_response_sampled: int = 0
    median_outsider_pr_size: int | None = None
    insiders_known: bool = False
    pr_source: str = "rest"
    committers_last_year: int | None = None
    newcomer_committers_last_year: int | None = None
    bus_factor: int | None = None
    beginner_label: str | None = None
    open_beginner_issues: int | None = None
    health_score: float = 0.0
    grade: str = "F"
    signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IssueCandidate(BaseModel):
    repo: str
    number: int
    title: str
    url: str
    labels: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    comments: int = 0
    author: str | None = None
    filed_by_maintainer: bool = False
    body_excerpt: str = ""
    availability: Availability = Availability.UNKNOWN
    availability_reason: str = ""
    assessment: IssueAssessment | None = None
    gsoc_org: str | None = None
    beginner_score: float = 0.0
    signals: list[str] = Field(default_factory=list)


class ContributionItem(BaseModel):
    """One PR, issue, thread, or review a contributor took part in."""

    kind: str  # pr | issue | discussion | review
    repo: str
    number: int
    title: str
    url: str
    state: str  # open | closed | merged
    author: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    comments: int = 0
    labels: list[str] = Field(default_factory=list)


class ContributionGuide(BaseModel):
    repo: str
    contributing_url: str | None = None
    contributing_excerpt: str = ""
    code_of_conduct_url: str | None = None
    toolchain: list[str] = Field(default_factory=list)
    devcontainer: bool = False
    setup_hints: list[str] = Field(default_factory=list)
    communication_channels: list[str] = Field(default_factory=list)
    beginner_issue_labels: list[str] = Field(default_factory=list)


class RepoLead(BaseModel):
    full_name: str
    url: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    pushed_at: datetime | None = None
    open_beginner_issues: int = 0
    ideas_mention: bool = False
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class ProjectIdea(BaseModel):
    """One project idea parsed from an org's ideas page. Empty fields were not on the page."""

    title: str
    section: str | None = None
    description: str = ""
    difficulty: str | None = None  # easy | medium | hard
    difficulty_raw: str = ""
    size: str | None = None  # small | medium | large
    hours: int | None = None
    size_raw: str = ""
    mentors: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    links: list[str] = Field(default_factory=list)
    confidence: str = "low"  # high | medium | low
    labelled_fields: int = 0
    source_url: str = ""
    match_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)


class IdeasDocument(BaseModel):
    source_url: str
    fetched_url: str
    layout: str = "unstructured"  # headings | index | unstructured | issues
    ideas: list[ProjectIdea] = Field(default_factory=list)
    # On an index page whose blocks are prose, the blocks themselves, used when
    # the links lead to no ideas.
    fallback_ideas: list[ProjectIdea] = Field(default_factory=list)
    sub_pages: list[dict[str, str]] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    ai_policy: list[str] = Field(default_factory=list)


class ProposalChecklistItem(BaseModel):
    id: str
    title: str
    description: str
    required: bool = True
    done: bool = False


class LogEntry(BaseModel):
    """One weekly note: the structure mentors expect in progress updates."""

    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    goal: str = ""
    done: str = ""
    links: list[str] = Field(default_factory=list)
    learned: str = ""
    stuck: str = ""
    next_step: str = ""

    def is_empty(self) -> bool:
        return not any([self.goal, self.done, self.links, self.learned, self.stuck, self.next_step])


class ProgressState(BaseModel):
    version: int = 1
    target_year: int = DEFAULT_TARGET_YEAR
    profile: dict[str, Any] = Field(default_factory=dict)
    phases: dict[str, bool] = Field(default_factory=dict)
    shortlisted_orgs: list[str] = Field(default_factory=list)
    tracked_repos: list[str] = Field(default_factory=list)
    tracked_issues: list[str] = Field(default_factory=list)
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    issue_status: dict[str, str] = Field(default_factory=dict)
    last_checked_at: datetime | None = None
    weekly_log: list[LogEntry] = Field(default_factory=list)
    updated_at: datetime | None = None


class Milestone(BaseModel):
    key: str
    label: str
    at: datetime
    project_size: str | None = None
    official: bool
    status: str
    days_until: int
    window_days: int | None = None


class ProgramPhase(BaseModel):
    id: str
    title: str
    advice: str


class OfficialSource(BaseModel):
    title: str
    url: HttpUrl | str
    why: str
