"""Shared Pydantic models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class JourneyPhase(StrEnum):
    LEARN = "learn"
    DISCOVER = "discover"
    EVALUATE = "evaluate"
    FIND_ISSUES = "find_issues"
    CONTRIBUTE = "contribute"
    COMMUNITY = "community"
    PROPOSAL = "proposal"
    TRACK = "track"


class Availability(StrEnum):
    AVAILABLE = "available"
    LIKELY_TAKEN = "likely_taken"
    ASSIGNED = "assigned"
    STALE = "stale"
    CLOSED = "closed"
    UNKNOWN = "unknown"


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
    has_contributing: bool = False
    has_code_of_conduct: bool = False
    has_ci: bool = False
    merge_rate: float | None = None
    median_pr_hours: float | None = None
    beginner_labels_present: bool = False
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
    body_excerpt: str = ""
    availability: Availability = Availability.UNKNOWN
    availability_reason: str = ""
    beginner_score: float = 0.0
    signals: list[str] = Field(default_factory=list)


class ContributionGuide(BaseModel):
    repo: str
    contributing_url: str | None = None
    contributing_excerpt: str = ""
    code_of_conduct_url: str | None = None
    setup_hints: list[str] = Field(default_factory=list)
    communication_channels: list[str] = Field(default_factory=list)
    beginner_issue_labels: list[str] = Field(default_factory=list)


class ProposalChecklistItem(BaseModel):
    id: str
    title: str
    description: str
    required: bool = True
    done: bool = False


class ProgressState(BaseModel):
    version: int = 1
    target_year: int = 2027
    profile: dict[str, Any] = Field(default_factory=dict)
    phases: dict[str, bool] = Field(default_factory=dict)
    shortlisted_orgs: list[str] = Field(default_factory=list)
    tracked_repos: list[str] = Field(default_factory=list)
    tracked_issues: list[str] = Field(default_factory=list)
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
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
