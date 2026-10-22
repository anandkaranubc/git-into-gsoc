"""Repository health scoring: how likely is a newcomer's PR to land here?"""

from __future__ import annotations

from datetime import UTC, datetime

from git_into_gsoc.models import HealthPoints, RepoHealth

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
# The most the single-commit newcomer count adds. It comes from ecosyste.ms, so when
# that service has no commit history for a repository the score leaves these points out
# instead of counting them as lost.
NEWCOMER_POINTS = 6
# Why a signal GitHub did not answer for is left out of the score.
UNREAD_WHY = "GitHub did not answer; run it again later"
# Up to this many changed lines, the median merged outside PR is a focused change.
FOCUSED_PR_LINES = 200


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

    The points add up to exactly 100, so every missing signal shows in the score and
    100 means every signal is at its best. (They once added up to 108 and were cut at
    100, which let a top repository lose a Code of Conduct, or all of its free
    beginner issues, without the score moving.) The grade bands leave room for a
    repository to miss a few points and still get an A. The outside merge rate is
    the strongest newcomer signal: when it is scored and low, it caps the grade (see
    OUTSIDER_CAPS). Stars add nothing: larger projects reject a higher share of
    newcomer PRs.
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    points: list[HealthPoints] = []
    dormant = False

    def award(signal: str, earned: float, most: float, why: str | None = None) -> None:
        # Every scored signal records its points, even zero, so `repo` can show where
        # the rest went. A signal with no line of its own (a missing Code of Conduct)
        # used to cost points without saying so.
        nonlocal score
        score += earned
        points.append(HealthPoints(signal=signal, earned=earned, most=most, why=why))

    if health.archived or health.disabled:
        health.health_score = 0.0
        health.grade = "F"
        health.warnings = ["Repository is archived or disabled; do not contribute here for GSoC"]
        health.signals = []
        health.notes = []
        health.points = []
        health.capped_by = "Archived or disabled, so it scores 0"
        return health

    pushed = 0.0
    if health.pushed_at:
        days = (datetime.now(UTC) - health.pushed_at.astimezone(UTC)).days
        # A push shows the code is alive, not that anyone reviews outside work; the
        # reply time below measures that, and DORMANT_CAP handles a silent year.
        if days <= 14:
            pushed = 16
            signals.append(f"Very recent activity ({days}d since push)")
        elif days <= 45:
            pushed = 12
            signals.append(f"Active ({days}d since push)")
        elif days <= 120:
            pushed = 6
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
    award("Recent push", pushed, 16)

    def past(text: str) -> str:
        """A pull request figure, marked as old when the repository has gone quiet."""
        return f"Before it went quiet: {text[0].lower()}{text[1:]}" if dormant else text

    unread = set(health.unread)
    if "community profile" in unread:
        # GitHub did not answer for the community profile, so these say nothing about
        # the repository: left out of the score, like missing ecosyste.ms data. A rate
        # limit used to read as no CONTRIBUTING guide, Code of Conduct, or templates.
        award("CONTRIBUTING guide", 0, 0, UNREAD_WHY)
        award("Code of Conduct", 0, 0, UNREAD_WHY)
        award("Issue or PR templates", 0, 0, UNREAD_WHY)
    else:
        if health.has_contributing:
            signals.append(
                "Has contributing rules in its README (no separate CONTRIBUTING file)"
                if health.contributing_source == "readme"
                else "Has a CONTRIBUTING guide"
            )
            award("CONTRIBUTING guide", 12, 12)
        elif "README" in unread:
            # No CONTRIBUTING file, and GitHub did not send the README that could hold
            # the guide instead.
            award("CONTRIBUTING guide", 0, 0, UNREAD_WHY)
        else:
            warnings.append("No CONTRIBUTING guide detected; ask maintainers how to start")
            award("CONTRIBUTING guide", 0, 12)
        if health.has_code_of_conduct:
            signals.append("Has a Code of Conduct")
        award("Code of Conduct", 4 if health.has_code_of_conduct else 0, 4)
        templates = health.has_issue_template or health.has_pr_template
        if templates:
            signals.append("Issue/PR templates guide contributions")
        award("Issue or PR templates", 4 if templates else 0, 4)
    if "workflows" in unread:
        award("CI on pull requests", 0, 0, UNREAD_WHY)
    else:
        if health.has_ci:
            signals.append("CI runs on pull requests")
        award("CI on pull requests", 8 if health.has_ci else 0, 8)

    if unread & {"labels", "beginner issues"}:
        award("Open beginner issues", 0, 0, UNREAD_WHY)
    else:
        open_issues = health.open_beginner_issues or 0
        free = open_issues - (health.assigned_beginner_issues or 0)
        beginner = 0.0
        if open_issues and free > 0:
            beginner = 10
            total = f" ({open_issues} open in total)" if free < open_issues else ""
            signals.append(
                f"{free} open '{health.beginner_label}' issue(s) nobody is assigned to{total}"
            )
        elif open_issues:
            beginner = 2
            warnings.append(
                f"All {open_issues} open '{health.beginner_label}' issue(s) are already assigned"
            )
        elif health.beginner_label:
            beginner = 4
            warnings.append(f"'{health.beginner_label}' label exists but no open issues use it")
        award(
            "Open beginner issues",
            beginner,
            10,
            None if health.beginner_label else "no beginner label found",
        )

    # Worth less than the outside merge rate below: most of these PRs come from the
    # core team, and the outside ones are counted again there.
    merged = 0.0
    if health.merge_rate is not None and health.prs_sampled >= 5:
        if health.merge_rate >= 0.5:
            merged = 8
            # A plain figure: "Healthy" over a 52% rate read as praise it had not earned.
            signals.append(past(f"{health.merge_rate:.0%} of human PRs merged"))
        elif health.merge_rate >= 0.25:
            merged = 4
            signals.append(past(f"{health.merge_rate:.0%} of human PRs merged"))
        else:
            warnings.append(f"Low merge rate ({health.merge_rate:.0%})")
        award("Merge rate of all human PRs", merged, 8)
    else:
        award("Merge rate of all human PRs", 0, 8, "too few closed PRs to score")

    rate = health.outsider_merge_rate
    sampled = health.outsider_prs_sampled
    cap = 100.0
    cap_reason: str | None = None
    if rate is not None and sampled >= MIN_OUTSIDER_SAMPLE:
        unmerged = sampled - round(rate * sampled)
        outside = 0.0
        if rate >= 0.4:
            outside = 12
            signals.append(past(f"Merges outside contributors' PRs ({rate:.0%} of {sampled})"))
        elif rate >= 0.2:
            outside = 6
            warnings.append(
                f"{unmerged} of the last {sampled} outside pull requests were not merged; "
                "ask on the issue before you start, and expect competition"
            )
        else:
            warnings.append(
                f"Rarely merges PRs from outside contributors ({rate:.0%} of {sampled}): "
                f"{unmerged} of the last {sampled} were not merged"
            )
        award("Outside merge rate", outside, 12)
        for below, limit in OUTSIDER_CAPS:
            if rate < below:
                cap = limit
                cap_reason = (
                    f"Under {below:.0%} of outside pull requests were merged, so the score "
                    f"stops at {limit:.0f}"
                )
                break
    else:
        if rate is not None and sampled:
            notes.append(
                f"Outside PRs merged: {rate:.0%} of {sampled} (too few to score; check recent PRs)"
            )
        award(
            "Outside merge rate",
            0,
            12,
            f"only {sampled} outside PRs, too few to score"
            if sampled
            else "no outside PRs sampled",
        )
    if health.outside_landed_elsewhere:
        notes.append(
            f"{health.outside_landed_elsewhere} closed outside PR(s) landed through a "
            "maintainer's own commit (counted as merged here; GitHub shows them as closed)"
        )
    award("Different outside authors merged", min(6.0, 2.0 * health.outside_authors_merged), 6)
    if health.outside_authors_merged:
        when = "" if dormant else " recently"
        signals.append(
            past(f"{health.outside_authors_merged} different outside author(s) merged{when}")
        )

    first = health.median_first_response_hours
    if first is not None and health.first_response_sampled < MIN_REPLY_SAMPLE:
        notes.append(
            f"First human reply on outside PRs: ~{_days_or_hours(first)} (median of only "
            f"{health.first_response_sampled}; not scored)"
        )
        first = None
    reply = 0.0
    reply_why: str | None = None
    if first is not None:
        # Time to the first human reply explains most of a PR's lifetime and
        # predicts whether newcomers keep contributing; prefer it over merge time.
        if first <= 24:
            reply = 10
            signals.append(
                past(
                    f"Pull requests from outsiders get a human reply within ~{first:.0f}h (median)"
                )
            )
        elif first <= 72:
            reply = 6
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
            # The team's own pull requests are in this figure too, so it can sit beside a
            # long wait for an outsider's first reply.
            notes.append(
                past(
                    f"Merged PRs, the team's included, land in "
                    f"~{_days_or_hours(health.median_pr_hours)} (median)"
                )
            )
    elif health.median_pr_hours is not None:
        if health.median_pr_hours <= 72:
            reply = 10
            signals.append(past(f"Merged PRs land fast (~{health.median_pr_hours:.0f}h median)"))
        elif health.median_pr_hours <= 240:
            reply = 5
            signals.append(past(f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median)"))
        else:
            warnings.append(
                f"Merged PRs take ~{health.median_pr_hours / 24:.0f}d (median); "
                "unmerged ones are not counted"
            )
    else:
        reply_why = "no reply or merge times measured"
    award("Time to a first human reply", reply, 10, reply_why)
    newcomers = health.newcomer_committers_last_year
    if newcomers is None:
        # No commit history from ecosyste.ms says nothing about the repository, so
        # score the rest out of what could be read. A year with no commits reads the
        # same way, and DORMANT_CAP already holds that repository down.
        notes.append(
            "ecosyste.ms, a free service that reads public commit histories, has none for "
            "this repository, so people who landed a single commit are left out of the score"
        )
        points.append(
            HealthPoints(
                signal="People who landed a single commit last year",
                earned=0,
                most=0,
                why="no commit history from ecosyste.ms",
            )
        )
    else:
        newcomer_points = 0.0
        if health.committers_last_year and newcomers >= 10:
            newcomer_points = NEWCOMER_POINTS
            signals.append(
                f"{newcomers} people landed their first and only commit in the last year "
                f"({health.committers_last_year} committers in total)"
            )
        elif health.committers_last_year and newcomers >= 3:
            newcomer_points = NEWCOMER_POINTS / 2
            signals.append(
                f"{newcomers} people landed a single commit in the last year "
                f"({health.committers_last_year} committers in total)"
            )
        elif health.committers_last_year:
            notes.append(f"{health.committers_last_year} people committed in the last year")
        award("People who landed a single commit last year", newcomer_points, NEWCOMER_POINTS)
    if health.bus_factor == 1:
        warnings.append("One person wrote more than half of last year's commits")

    size = health.median_outsider_pr_size
    if size is not None:
        # A median of thousands of lines (notebooks, data) is not a focused change.
        focused = ", so focused changes are what land here" if size <= FOCUSED_PR_LINES else ""
        notes.append(past(f"Merged outside PRs change ~{size} lines (median){focused}"))

    if health.license == "Other":
        # GitHub's name for a license file it cannot match to a known license.
        notes.append(
            "GitHub found a license file but cannot tell which license it is; "
            "read it to check that the code is open source"
        )
    elif health.license:
        signals.append(f"License: {health.license}")
    else:
        warnings.append("No license detected")
    award("License", 4 if health.license else 0, 4)

    # Stars carry no points: popularity predicts competition, not acceptance.
    if health.stars < 20:
        warnings.append("Very small project; confirm it is still maintained")
    elif health.stars > 50000:
        warnings.append("Very popular repo: beginner issues go fast, expect competition")

    if dormant and cap > DORMANT_CAP:
        cap = DORMANT_CAP
        cap_reason = (
            f"Nothing was pushed for over {DORMANT_DAYS} days, so the score stops at "
            f"{DORMANT_CAP:.0f}"
        )
    if unread:
        parts = sorted(unread)
        notes.append(
            f"GitHub did not answer for its {', '.join(parts)}, so the signals that come from "
            f"{'it' if len(parts) == 1 else 'them'} are left out of the score; run it again "
            "later for a full grade"
        )
    # Out of what could be read: missing ecosyste.ms data leaves its points out.
    out_of = sum(p.most for p in points)
    uncapped = score * 100 / out_of
    health.health_score = round(min(uncapped, cap), 1)
    health.grade = _grade(health.health_score)
    health.signals = signals
    health.warnings = warnings
    health.notes = notes
    health.points = points
    health.capped_by = cap_reason if uncapped > cap else None
    return health
