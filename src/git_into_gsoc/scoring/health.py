"""Repository health scoring: how likely is a newcomer's PR to land here?"""

from __future__ import annotations

from datetime import UTC, datetime

from git_into_gsoc.models import RepoHealth

MIN_OUTSIDER_SAMPLE = 10  # below this, the outsider merge rate is shown but not scored
MIN_REPLY_SAMPLE = 5  # below this, the first-reply time is shown but not scored
# A repository that turns down most outside pull requests cannot grade well, however
# polished it looks: below 40% merged it tops out at B, below 20% at C.
OUTSIDER_CAPS = ((0.2, 71.0), (0.4, 84.0))
# A repository with nothing pushed for longer than this may never review a pull request.
DORMANT_DAYS = 365
# Its pull request figures come from before it went quiet, so they cannot lift it above
# a D ("Risky") however good they look.
DORMANT_CAP = 57.0


def _days_or_hours(hours: float) -> str:
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.0f}d"


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    if score >= 58:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def score_repo_health(health: RepoHealth) -> RepoHealth:
    """Score how likely a newcomer's pull request is to land, out of 100.

    The points add up to 108 and the total is capped at 100, so a repository can
    miss one minor signal and still score 100. The outside merge rate is the
    strongest newcomer signal: when it is scored and low, it caps the grade (see
    OUTSIDER_CAPS). Stars add nothing: larger projects reject a higher share of
    newcomer PRs.
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []
    dormant = False

    if health.archived or health.disabled:
        health.health_score = 0.0
        health.grade = "F"
        health.warnings = ["Repository is archived or disabled; do not contribute here for GSoC"]
        health.signals = []
        return health

    if health.pushed_at:
        days = (datetime.now(UTC) - health.pushed_at.astimezone(UTC)).days
        if days <= 14:
            score += 20
            signals.append(f"Very recent activity ({days}d since push)")
        elif days <= 45:
            score += 15
            signals.append(f"Active ({days}d since push)")
        elif days <= 120:
            score += 7
            signals.append(f"Somewhat active ({days}d since push)")
        elif days <= DORMANT_DAYS:
            warnings.append(f"Stale repository ({days}d since last push)")
        else:
            # The figures below come from the last closed pull requests, however old: a
            # Processing library quiet for 851 days still read "reply within ~20h".
            dormant = True
            warnings.append(
                f"Nothing has been pushed for {days} days, so the pull request figures here "
                "are from before then and a new pull request may get no reply"
            )
    else:
        warnings.append("Missing push timestamp")

    def past(text: str) -> str:
        """A pull request figure, marked as old when the repository has gone quiet."""
        return f"Before it went quiet: {text[0].lower()}{text[1:]}" if dormant else text

    if health.has_contributing:
        score += 12
        signals.append("Has a CONTRIBUTING guide")
    else:
        warnings.append("No CONTRIBUTING guide detected; ask maintainers how to start")
    if health.has_code_of_conduct:
        score += 4
        signals.append("Has a Code of Conduct")
    if health.has_issue_template or health.has_pr_template:
        score += 4
        signals.append("Issue/PR templates guide contributions")
    if health.has_ci:
        score += 8
        signals.append("CI runs on pull requests")

    open_issues = health.open_beginner_issues or 0
    free = open_issues - (health.assigned_beginner_issues or 0)
    if open_issues and free > 0:
        score += 10
        total = f" ({open_issues} open in total)" if free < open_issues else ""
        signals.append(
            f"{free} open '{health.beginner_label}' issue(s) nobody is assigned to{total}"
        )
    elif open_issues:
        score += 2
        warnings.append(
            f"All {open_issues} open '{health.beginner_label}' issue(s) are already assigned"
        )
    elif health.beginner_label:
        score += 4
        warnings.append(f"'{health.beginner_label}' label exists but no open issues use it")

    if health.merge_rate is not None and health.prs_sampled >= 5:
        if health.merge_rate >= 0.5:
            score += 12
            signals.append(past(f"Healthy merge rate ({health.merge_rate:.0%} of human PRs)"))
        elif health.merge_rate >= 0.25:
            score += 6
            signals.append(past(f"Moderate merge rate ({health.merge_rate:.0%})"))
        else:
            warnings.append(f"Low merge rate ({health.merge_rate:.0%})")

    rate = health.outsider_merge_rate
    sampled = health.outsider_prs_sampled
    cap = 100.0
    if rate is not None and sampled >= MIN_OUTSIDER_SAMPLE:
        unmerged = sampled - round(rate * sampled)
        if rate >= 0.4:
            score += 12
            signals.append(past(f"Merges outside contributors' PRs ({rate:.0%} of {sampled})"))
        elif rate >= 0.2:
            score += 6
            warnings.append(
                f"{unmerged} of the last {sampled} outside pull requests were not merged; "
                "ask on the issue before you start, and expect competition"
            )
        else:
            warnings.append(
                f"Rarely merges PRs from outside contributors ({rate:.0%} of {sampled}): "
                f"{unmerged} of the last {sampled} were not merged"
            )
        cap = next((limit for below, limit in OUTSIDER_CAPS if rate < below), cap)
    elif rate is not None and sampled:
        signals.append(
            f"Outside PRs merged: {rate:.0%} of {sampled} (too few to score; check recent PRs)"
        )
    if health.outside_landed_elsewhere:
        signals.append(
            f"{health.outside_landed_elsewhere} closed outside PR(s) landed through a "
            "maintainer's own commit (counted as merged here; GitHub shows them as closed)"
        )
    if health.outside_authors_merged:
        score += min(6.0, 2.0 * health.outside_authors_merged)
        when = "" if dormant else " recently"
        signals.append(
            past(f"{health.outside_authors_merged} different outside author(s) merged{when}")
        )

    first = health.median_first_response_hours
    if first is not None and health.first_response_sampled < MIN_REPLY_SAMPLE:
        signals.append(
            f"First human reply on outside PRs: ~{_days_or_hours(first)} (median of only "
            f"{health.first_response_sampled}; not scored)"
        )
        first = None
    if first is not None:
        # Time to the first human reply explains most of a PR's lifetime and
        # predicts whether newcomers keep contributing; prefer it over merge time.
        if first <= 24:
            score += 10
            signals.append(
                past(
                    f"Pull requests from outsiders get a human reply within ~{first:.0f}h (median)"
                )
            )
        elif first <= 72:
            score += 6
            signals.append(
                past(
                    f"Pull requests from outsiders get a human reply in ~{first / 24:.0f}d (median)"
                )
            )
        else:
            warnings.append(
                f"Pull requests from outsiders wait ~{first / 24:.0f}d for a first human reply (median)"
            )
        if health.median_pr_hours is not None:
            signals.append(
                past(f"Merged PRs land in ~{_days_or_hours(health.median_pr_hours)} (median)")
            )
    elif health.median_pr_hours is not None:
        if health.median_pr_hours <= 72:
            score += 10
            signals.append(past(f"Merged PRs land fast (~{health.median_pr_hours:.0f}h median)"))
        elif health.median_pr_hours <= 240:
            score += 5
            signals.append(past(f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median)"))
        else:
            warnings.append(
                f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median); "
                "unmerged ones are not counted"
            )
    newcomers = health.newcomer_committers_last_year
    if newcomers is not None and health.committers_last_year:
        if newcomers >= 10:
            score += 6
            signals.append(
                f"{newcomers} people landed their first and only commit in the last year "
                f"({health.committers_last_year} committers in total)"
            )
        elif newcomers >= 3:
            score += 3
            signals.append(
                f"{newcomers} people landed a single commit in the last year "
                f"({health.committers_last_year} committers in total)"
            )
        else:
            signals.append(f"{health.committers_last_year} people committed in the last year")
    if health.bus_factor == 1:
        warnings.append("One person wrote more than half of last year's commits")

    if health.median_outsider_pr_size is not None:
        signals.append(
            past(
                f"Merged outside PRs change ~{health.median_outsider_pr_size} lines (median), "
                "so focused changes are what land here"
            )
        )

    if health.license:
        score += 4
        signals.append(f"License: {health.license}")
    else:
        warnings.append("No license detected")

    # Stars carry no points: popularity predicts competition, not acceptance.
    if health.stars < 20:
        warnings.append("Very small project; confirm it is still maintained")
    elif health.stars > 50000:
        warnings.append("Very popular repo: beginner issues go fast, expect competition")

    if dormant:
        cap = min(cap, DORMANT_CAP)
    health.health_score = round(min(score, cap, 100.0), 1)
    health.grade = _grade(health.health_score)
    health.signals = signals
    health.warnings = warnings
    return health
