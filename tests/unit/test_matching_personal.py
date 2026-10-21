"""Evidence summaries, and fitting ideas, issues, repositories, and a path to one person."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from git_into_gsoc.github.repos import repo_lead_score
from git_into_gsoc.gsoc.project_ideas import rank_ideas
from git_into_gsoc.matching.ideas import ideas_for, required_skills
from git_into_gsoc.matching.issues import is_event_repo, issue_fit, personalize
from git_into_gsoc.matching.path import learning_path
from git_into_gsoc.matching.profile import build_profile
from git_into_gsoc.matching.signals import language_concepts, summarize_ideas, summarize_repos
from git_into_gsoc.models import ProjectIdea

NOW = datetime(2026, 10, 21, tzinfo=UTC)


def test_ideas_summary_counts_what_the_page_states() -> None:
    ideas = [
        {
            "title": "Accessible dropdown in Vue",
            "difficulty": "easy",
            "size": "small",
            "skills": ["HTML/CSS", "JavaScript"],
            "mentors": ["Ana", "Bo"],
            "description": "Screen reader support",
        },
        {
            "title": "Port the parser to Rust",
            "difficulty": "hard",
            "skills": ["rust"],
            "mentors": ["Ana"],
        },
        {"title": "Untitled", "description": ""},
    ]
    summary = summarize_ideas(ideas, layout="headings", url="https://example.org/ideas")
    assert summary["count"] == 3
    assert summary["difficulty"] == {"easy": 1, "hard": 1}
    assert summary["size"] == {"small": 1}
    assert summary["skills"]["css"] == 1 and summary["skills"]["rust"] == 1
    assert summary["mentions"]["accessibility"] == 1  # "screen reader" in the description
    assert summary["mentors"] == 2
    assert summary["ideas"][0] == {
        "t": "Accessible dropdown in Vue",
        "d": "easy",
        "s": "small",
        "k": ["css", "html", "javascript", "accessibility", "vue"],
    }


def test_repository_summary_keeps_only_active_code() -> None:
    fresh = (NOW - timedelta(days=10)).isoformat()
    stale = (NOW - timedelta(days=500)).isoformat()
    repos = [
        {"language": "Python", "pushed_at": fresh, "topics": ["astronomy"], "description": ""},
        {
            "language": "Jupyter Notebook",
            "pushed_at": fresh,
            "topics": [],
            "description": "Telescope tools",
        },
        {"language": "C", "pushed_at": stale, "topics": []},
        {"language": "Python", "pushed_at": fresh, "archived": True},
        {"language": "Python", "pushed_at": fresh, "fork": True},
    ]
    summary = summarize_repos(repos, ["star-lab"], now=NOW)
    assert summary["active_repos"] == 2
    assert summary["languages"] == {"Jupyter Notebook": 1, "Python": 1}
    assert summary["concepts"]["astronomy"] == 2
    assert language_concepts(summary["languages"]) == {"python": 2}
    assert language_concepts({"Pyhton": 3}) == {}  # GitHub's names are exact; never guess


def _signals_ideas() -> list[dict[str, object]]:
    return [
        {
            "t": "Accessible dropdown",
            "d": "easy",
            "s": "small",
            "k": ["css", "html", "vue", "accessibility"],
        },
        {
            "t": "Rewrite the renderer",
            "d": "hard",
            "s": "large",
            "k": ["c++", "opengl", "graphics"],
        },
        {"t": "Theme editor", "d": "medium", "s": "medium", "k": ["css", "javascript", "design"]},
    ]


def test_ideas_that_fit_say_what_you_have_and_what_you_would_learn() -> None:
    def pick(hours: int) -> list[dict[str, object]]:
        person = build_profile(
            technologies=["html", "css"],
            interests=["accessibility"],
            experience="new",
            hours_per_week=hours,
        )
        return ideas_for(_signals_ideas(), person, year=2026, source_url="https://x/ideas")

    roomy = pick(8)
    assert [i["title"] for i in roomy] == ["Accessible dropdown", "Theme editor"]
    first = roomy[0]
    assert first["you_have"] == ["CSS", "HTML"] and first["you_would_learn"] == ["Vue"]
    assert first["matches_interests"] == ["Accessibility"]
    assert "stated difficulty: easy" in first["stated"] and first["year"] == 2026
    # 175 hours do not fit in 22 weeks at 6 hours a week, so the medium idea drops out.
    assert [i["title"] for i in pick(6)] == ["Accessible dropdown"]


def test_rank_ideas_matches_concepts_not_letters() -> None:
    # On GNOME's page, skill "c" scored a Rust idea first because "c" is in "requires".
    rust = ProjectIdea(
        title="Pitivi effects", description="requires Rust", skills=["Rust", "GStreamer"]
    )
    crosswords = ProjectIdea(title="Crosswords", description="C and GLib", skills=["C", "GLib"])
    ranked = rank_ideas([rust, crosswords], skills=["c", "gtk", "python"])
    assert ranked[0].title == "Crosswords"
    assert ranked[0].match_reasons[0].startswith("Skills match: C")
    assert ranked[1].match_reasons == ["Requires Rust, which you did not list"]
    assert "Rust" in ranked[1].skills_to_learn


def test_issues_are_ordered_by_what_the_person_brings_but_free_ones_stay_first() -> None:
    person = build_profile(technologies=["css"], interests=["accessibility"], experience="new")
    issues = [
        {
            "repo": "a/b",
            "number": 1,
            "title": "Refactor the cache",
            "availability": "available",
            "beginner_score": 70,
        },
        {
            "repo": "a/b",
            "number": 2,
            "title": "Fix CSS contrast for screen readers",
            "availability": "available",
            "beginner_score": 62,
        },
        {
            "repo": "a/b",
            "number": 3,
            "title": "Fix CSS colours",
            "availability": "claimed",
            "beginner_score": 90,
        },
        {
            "repo": "a/b",
            "number": 4,
            "title": "Fix typo in docs",
            "labels": ["documentation"],
            "availability": "available",
            "beginner_score": 60,
        },
    ]
    ordered = personalize(issues, person)
    assert ordered[0]["number"] == 2
    assert ordered[-1]["number"] == 3  # claimed, however well it fits
    assert ordered[0]["fits_you"][:2] == [
        "Names CSS, which you know",
        "About Accessibility, one of your interests",
    ]
    docs = next(i for i in ordered if i["number"] == 4)
    assert "A documentation or test change: a gentle first pull request" in docs["fits_you"]
    assert personalize(issues, build_profile()) == issues  # nothing to personalise


def test_learning_path_changes_with_experience_and_hours() -> None:
    orgs = [{"name": 'Star "Lab"', "skills_to_learn": ["C++ (3 of 9 ideas)"]}]
    new = learning_path(
        build_profile(technologies=["python"], experience="new", hours_per_week=5), orgs
    )
    steps = [s["step"] for s in new]
    assert steps[0].startswith("Practise the pull request routine")
    assert any("documentation, test, or small bug" in s for s in steps)
    assert any(s.startswith("Learn C++ from the code") for s in steps)
    assert steps[-1].startswith("At 5 hours a week")
    assert [s["n"] for s in new] == list(range(1, len(new) + 1))
    assert all(
        '"Star Lab"' in (s["command"] or '"Star Lab"') for s in new if "org" in (s["command"] or "")
    )
    expert = learning_path(build_profile(technologies=["python"], experience="experienced"), orgs)
    assert not expert[0]["step"].startswith("Practise")
    assert any("review an open pull request" in s["step"] for s in expert)


def test_repositories_that_match_the_person_rank_higher_and_big_ones_say_so() -> None:
    pushed = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    base = {"pushed_at": pushed, "stargazers_count": 50}
    person = build_profile(technologies=["typescript"], interests=["accessibility"])
    web = base | {"language": "TypeScript", "topics": ["a11y"], "description": "UI kit"}
    other = base | {
        "language": "Go",
        "topics": [],
        "description": "Build server",
        "size": 2_500_000,
    }
    web_score, web_reasons = repo_lead_score(
        web, beginner_issues=0, ideas_mention=False, language=None, person=person
    )
    other_score, other_reasons = repo_lead_score(
        other, beginner_issues=0, ideas_mention=False, language=None, person=person
    )
    assert web_score > other_score
    assert "Uses TypeScript, which you know" in web_reasons
    assert "About Accessibility, which you care about" in web_reasons
    assert any(r.startswith("Large repository (about 2.5 GB)") for r in other_reasons)


def test_an_unticked_template_box_is_not_what_the_issue_is_about() -> None:
    # p5.js issue templates list every sub-area with a checkbox; only ticked ones count.
    person = build_profile(technologies=["javascript"], interests=["accessibility"])
    template = (
        "Most appropriate sub-area of p5.js? - [ ] Accessibility - [ ] Color - [x] WebGL "
        "- [ ] Typography Details: the filter shader breaks on resize"
    )
    issue = {"title": "WebGL filter stress test", "body_excerpt": template}
    _, reasons = issue_fit(issue, person)
    assert not any("Accessibility" in r for r in reasons)
    ticked = {"title": "Alt text", "body_excerpt": "- [x] Accessibility Screen readers skip it"}
    assert any("Accessibility" in r for r in issue_fit(ticked, person)[1])


def test_find_issues_order_stands_and_only_recommend_reorders() -> None:
    person = build_profile(technologies=["css"])
    issues = [
        {
            "repo": "own/a",
            "number": 1,
            "title": "Refactor",
            "availability": "available",
            "beginner_score": 60,
        },
        {
            "repo": "linked/b",
            "number": 2,
            "title": "Fix CSS",
            "availability": "available",
            "beginner_score": 60,
        },
        {
            "repo": "x/c",
            "number": 3,
            "title": "Fix CSS too",
            "availability": "unknown",
            "beginner_score": 90,
        },
    ]
    kept = personalize(issues, person, reorder=False)
    assert [i["number"] for i in kept] == [1, 2, 3]
    assert kept[1]["fits_you"] == ["Names CSS, which you know"]
    # Reordered: verified free issues first; one whose history could not be checked waits.
    assert [i["number"] for i in personalize(issues, person)] == [2, 1, 3]


def test_repository_topics_are_read_one_by_one() -> None:
    pushed = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    repo = {"pushed_at": pushed, "language": "TypeScript", "topics": ["react", "frontend"]}
    _, reasons = repo_lead_score(
        repo,
        beginner_issues=0,
        ideas_mention=False,
        language=None,
        person=build_profile(technologies=["react"]),
    )
    assert "Uses React, which you know" in reasons


def test_an_idea_that_requires_a_skill_you_lack_ranks_below_one_you_can_start() -> None:
    # GNOME's page: Pitivi "Experience with Rust and GTK4 is required" ranked above the
    # C/GLib Crosswords idea for someone who knows C, Python, and GTK.
    pitivi = ProjectIdea(
        title="Pitivi effects",
        description="Experience with Rust and GTK4 is required for this project. "
        "Familiarity with Python, GES and GStreamer is a plus.",
        skills=["Rust", "GTK", "Python"],
    )
    crosswords = ProjectIdea(
        title="Crosswords puzzles",
        description="Experience with C / GLib-style programming is required.",
        skills=["C"],
    )
    ranked = rank_ideas([pitivi, crosswords], skills=["c", "python", "gtk"])
    assert [i.title for i in ranked] == ["Crosswords puzzles", "Pitivi effects"]
    assert "Requires Rust, which you did not list" in ranked[1].match_reasons
    assert "You have the skills it says are required" in ranked[0].match_reasons


def test_required_skills_need_the_capital_letter_for_short_names() -> None:
    assert required_skills("You are required to go through the docs first.") == []
    assert required_skills("Knowledge of Go is required. Python helps.") == ["go"]
    assert set(required_skills("Required skills: C and C++")) == {"c", "c++"}


def test_event_repositories_are_not_projects() -> None:
    # recommend offered numfocus/disc-unconference-2023-projects#25 as a starter issue.
    for name in (
        "numfocus/disc-unconference-2023-projects",
        "org/hackathon",
        "org/gsoc-2026",
        "x/talks",
    ):
        assert is_event_repo(name), name
    for name in ("zulip/zulip-terminal", "sympy/sympy", "org/eventlet", "org/py2026parser"):
        assert not is_event_repo(name), name
