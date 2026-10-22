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
    assert summary["count"] == 2  # "Untitled" is a fragment, not an idea
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
    fitting = [{"org": 'Star "Lab"', "ideas": [{"you_would_learn": ["C++", "CMake"]}]}]
    new = learning_path(
        build_profile(technologies=["python"], experience="new", hours_per_week=5), orgs, fitting
    )
    steps = [s["step"] for s in new]
    # At 5 hours a week the pace comes first, with the weeks worked out.
    assert steps[0].startswith("Plan around 5 hours a week: plan for a 90-hour project")
    assert "about 18 weeks" in steps[0] and "at most 22 weeks" in steps[0]
    assert steps[1].startswith("Practise the pull request routine")
    assert any("documentation, test, or small bug" in s for s in steps)
    assert any(s.startswith("Learn the basics of C++") for s in steps)
    # No learning step without ideas that fit: a page's whole skill list is not a plan.
    plain = learning_path(build_profile(technologies=["python"]), orgs)
    assert not any(s["step"].startswith("Learn") for s in plain)
    assert steps[-1].startswith("Draft your proposal early")
    assert any("projects --org" in (s["command"] or "") for s in new)
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


def test_headings_and_fragments_are_not_ideas() -> None:
    from git_into_gsoc.matching.ideas import is_real_idea

    for title in (
        "Description",
        "Benefit to Fedora",
        "Project 2",
        "Brief Explanation[επεξεργασία | επεξεργασία κώδικα]",
        "Why did we replace p4c-behavioral with bmv2?",
        "Integrated Faust Language Server [Taken in 2025]",
        "Flutter",
    ):
        assert not is_real_idea(title), title
    assert is_real_idea("Implement an accessible, multi-select dropdown component")
    assert is_real_idea("GDB", labelled=True)  # a short title with a stated size is kept


def test_starter_issues_that_are_not_first_tasks_are_screened_out() -> None:
    from git_into_gsoc.matching.issues import starter_problem

    c_dev = build_profile(technologies=["c", "assembly"])
    assert starter_problem({"title": "No GSoC on Wagtail core in 2027"}, c_dev)
    assert starter_problem({"title": "Spark Operator Roadmap 2024"}, c_dev)
    assert starter_problem({"title": "What can I work on ?"}, c_dev)
    assert starter_problem({"title": "Progress", "labels": ["epic"]}, c_dev)
    assert starter_problem({"title": "add CI for Mac", "created_at": "2016-03-01"}, c_dev)
    flake8 = {"title": "Fix currently ignored Flake8 warnings", "created_at": "2025-01-01"}
    assert "which you did not list" in str(starter_problem(flake8, c_dev))
    fine = {"title": "Fix a null pointer in the C parser", "created_at": "2025-06-01"}
    assert starter_problem(fine, c_dev) is None


def test_more_page_furniture_and_repeats_are_not_ideas() -> None:
    from git_into_gsoc.matching.ideas import is_real_idea

    for title in (
        "Details of your coding project",
        "📌 See the official timeline for more details.",
        "✅ (DONE) Port the docs",
        "How To Test",
        "Folders and files",
    ):
        assert not is_real_idea(title), title
    person = build_profile(technologies=["css"], interests=["accessibility"])
    twice = [{"t": "Accessible dropdown component", "k": ["css", "accessibility"]}] * 2
    assert len(ideas_for(twice, person, year=2026, source_url=None)) == 1


def test_labels_that_say_not_ready_keep_an_issue_off_the_starter_list() -> None:
    from git_into_gsoc.matching.issues import starter_problem

    person = build_profile(technologies=["javascript"])
    for labels in (["intermediate"], ["Can't reproduce"], ["needs triage"], ["duplicate"]):
        issue = {"title": "Fix map drawing", "labels": labels, "created_at": "2025-05-01"}
        assert starter_problem(issue, person), labels
    fine = {"title": "Fix map drawing", "labels": ["good first issue"], "created_at": "2025-05-01"}
    assert starter_problem(fine, person) is None


def test_the_path_never_says_learn_the_organizations_own_product() -> None:
    orgs = [{"name": "Blender Foundation"}]
    fitting = [{"org": "Blender Foundation", "ideas": [{"you_would_learn": ["Blender", "Python"]}]}]
    steps = [s["step"] for s in learning_path(build_profile(technologies=["c++"]), orgs, fitting)]
    assert any(s.startswith("Learn the basics of Python") for s in steps)
    assert not any("Blender with" in s for s in steps)


def test_governance_test_and_reserved_issues_are_not_first_tasks() -> None:
    from git_into_gsoc.matching.issues import is_not_code_repo, starter_problem

    for repo in (
        "webpack/tsc",
        "webpack/working-groups",
        "learningequality/test-actions",
        "zulip/.github",
    ):
        assert is_not_code_repo(repo), repo
    assert not is_not_code_repo("sympy/sympy")
    person = build_profile(technologies=["rust"])
    reserved = {
        "repo": "boa-dev/boa",
        "title": "Audit the string handling",
        "body_excerpt": "This issue is reserved for GSoC candidates.",
        "created_at": "2026-01-01",
    }
    assert starter_problem(reserved, person) == "reserved for someone or already being worked on"


def test_a_program_word_marks_an_application_repo_only_as_its_first_word() -> None:
    # A launch audit found `issue anandkaranubc/git-into-gsoc#166`, the check
    # CONTRIBUTING asks for, calling this project "a governance, test, or sandbox
    # repository" because its name contains "gsoc".
    from git_into_gsoc.matching.issues import is_not_code_repo, starter_problem

    for repo in (
        "learning-unlimited/gsoc",
        "example/gsoc2026",
        "example/GSoC-2026-ideas",
        "example/gsoc_ideas",
        "example/google-summer-of-code",
        "example/outreachy-2025",
        # Right after the owner's own name: an organization's own GSoC repository.
        "pharo-project/pharo-gsoc",
        "ML4SCI/ML4SCI_GSoC",
        "processing/Processing-Foundation-GSoC",
        "processing/processing-gsoc-archive",
    ):
        assert is_not_code_repo(repo), repo
    for repo in (
        "anandkaranubc/git-into-gsoc",
        "example/foo-gsoc-tools",
        "example/gsocial",
        "example/project-gsoc-tools",
        # A project built in a GSoC year is still code.
        "RocketChat/CodeReviewAgent_GSoC2025",
        "ga4gh/ga4gh_workflow_clinic_gsoc_2026",
    ):
        assert not is_not_code_repo(repo), repo
    issue = {
        "repo": "anandkaranubc/git-into-gsoc",
        "title": "Explain the bus factor at first use",
        "labels": ["good first issue", "documentation"],
        "created_at": "2026-10-20T00:00:00Z",
    }
    assert starter_problem(issue, build_profile(technologies=["python"])) is None


def test_help_wanted_alone_medium_and_unsettled_issues_are_not_first_tasks() -> None:
    from git_into_gsoc.matching.issues import starter_problem

    person = build_profile(technologies=["rust"])

    def issue(*labels: str, title: str = "Fix the parser") -> dict[str, object]:
        return {"title": title, "labels": list(labels), "created_at": "2026-01-01"}

    assert "no beginner label" in str(starter_problem(issue("Help Wanted", "A-API"), person))
    assert starter_problem(issue("good first issue", "E-Medium"), person)
    assert starter_problem(issue("good first issue", "status: needs discussion"), person)
    calls = issue("good first issue", title="Find bugs in the rewrite of the assumption system")
    assert "call for testing" in str(starter_problem(calls, person))
    # A beginner label beside "help wanted" is fine, and so is a medium priority.
    assert starter_problem(issue("good first issue", "help wanted"), person) is None
    assert starter_problem(issue("Easy to Fix", "priority: medium"), person) is None


def test_issues_others_asked_for_stay_off_the_starter_list() -> None:
    from git_into_gsoc.matching.issues import starter_problem

    person = build_profile(technologies=["python"])

    def asked(*claims: dict[str, object]) -> dict[str, object]:
        return {
            "title": "Fix the parser",
            "labels": ["good first issue"],
            "created_at": "2026-01-01",
            "author": "opener",
            "assessment": {"claims": list(claims)},
        }

    # Three people over two years: crowded, though each claim is old.
    crowded = asked(
        {"login": "a", "days_ago": 240}, {"login": "b", "days_ago": 340}, {"login": "c"}
    )
    assert starter_problem(crowded, person) == "3 people have asked to work on it"
    # The author said "I'm working on this" 73 days ago: stale for `issue`, still theirs.
    mine = asked({"login": "Opener", "days_ago": 73})
    assert starter_problem(mine, person) == "its author said they are working on it"
    granted = asked({"login": "a", "days_ago": 128, "granted": True})
    assert "a maintainer gave it to someone" in str(starter_problem(granted, person))
    # One ask from someone else 56 days ago, never approved: still a fair first task.
    assert starter_problem(asked({"login": "a", "days_ago": 56}), person) is None
    assert starter_problem(asked(), person) is None


def test_go_as_an_english_verb_is_not_the_language() -> None:
    from git_into_gsoc.matching.concepts import find_concepts

    assert "go" not in find_concepts("3. Go to profile screen. Go back and tap again.")
    assert "go" in find_concepts("Port the CLI to Go. Go is fast.")


def test_an_android_app_issue_suits_someone_who_knows_kotlin() -> None:
    from git_into_gsoc.matching.issues import starter_problem

    crash = {
        "title": "App crashes when tapping on a card in landscape mode",
        "body_excerpt": "Steps: 1. Open the app 2. Go to profile screen. Android Version: 16",
        "labels": ["bug", "good first issue"],
        "created_at": "2026-05-01",
    }
    assert starter_problem(crash, build_profile(technologies=["kotlin"])) is None
    assert starter_problem(crash, build_profile(technologies=["haskell"]))


def test_the_path_goes_through_mentors_when_the_top_organization_has_no_starter_issue() -> None:
    orgs = [{"name": "ML4SCI", "github_orgs": ["ML4SCI"]}]
    person = build_profile(technologies=["python"], experience="new")
    empty = learning_path(person, orgs, top_has_starter=False)
    commands = " ".join(s["command"] for s in empty)
    assert "issues --org" not in commands
    assert any("mentors" in s["step"] for s in empty)
    usual = learning_path(person, orgs, top_has_starter=True)
    assert any("issues --org" in s["command"] for s in usual)


def test_a_starter_issue_counts_for_the_top_organization_by_name_or_owner() -> None:
    from git_into_gsoc.service import _has_starter

    orgs = [{"name": "AnkiDroid", "github_orgs": ["ankidroid"]}, {"name": "Kiwix"}]
    assert _has_starter(orgs, [{"repo": "ankidroid/Anki-Android"}])
    assert _has_starter(orgs, [{"repo": "x/y", "gsoc_org": "AnkiDroid"}])
    assert not _has_starter(orgs, [{"repo": "kiwix/kiwix-android", "gsoc_org": "Kiwix"}])
    assert _has_starter([], []) is None


def test_a_broad_interest_is_not_widened_to_every_part_of_it() -> None:
    from git_into_gsoc.matching.ideas import wanted_domains

    websites = wanted_domains(build_profile(interests=["websites"]))
    assert "web" in websites and "backend" not in websites  # websites is not caring about APIs
    robots = wanted_domains(build_profile(interests=["robotics"]))
    assert "robotics" in robots


def test_the_path_says_where_the_program_is_and_links_an_unreadable_ideas_page() -> None:
    orgs = [
        {
            "name": "Quiet Lab",
            "ideas_url": "https://quiet.example/ideas",
            "ideas_unread": True,
        }
    ]
    person = build_profile(technologies=["python"], experience="new", hours_per_week=10)
    program = {"target_year": 2027, "list_year": 2026, "confirmed": False}
    path = learning_path(person, orgs, top_has_starter=False, program=program)
    assert path[0]["command"] == "git-into-gsoc program"
    assert "from 2026" in path[0]["why"]
    # At 10 hours a week a 175-hour project fits in 18 weeks.
    assert path[1]["step"].startswith("Plan around 10 hours a week: a 175-hour project fits")
    mentors = next(s for s in path if s["step"].startswith("Ask its mentors"))
    assert mentors["command"] == "Open https://quiet.example/ideas"
    confirmed = learning_path(person, orgs, program={**program, "confirmed": True})
    assert confirmed[0]["step"].startswith("Check the GSoC 2027 timeline")


def test_too_few_hours_for_any_project_is_said_plainly() -> None:
    path = learning_path(build_profile(technologies=["python"], hours_per_week=3), [])
    assert path[0]["step"].startswith("Plan around 3 hours a week: even a 90-hour project")
    assert "find more hours" in path[0]["step"]


def test_the_pace_leaves_room_and_says_when_the_mentor_must_agree() -> None:
    from git_into_gsoc.matching.path import _pace

    # 8 hours: 175 hours is 22 weeks, the very limit, so plan for 90 (12 weeks).
    assert _pace(8).startswith("plan for a 90-hour project (about 12 weeks)")
    # 10 hours: 175 hours in 18 weeks fits, but only with a longer timeline.
    assert _pace(10).startswith("a 175-hour project fits in about 18 weeks")
    assert "your mentor has to agree to" in _pace(10)
    assert _pace(15).startswith("a 175-hour project fits the standard 12 weeks")
    assert "find more hours" in _pace(4)
    # 4 and 3 hours: 23 and 30 weeks are past the limit, not merely close to it.
    assert "longer than the 22-week limit" in _pace(4) and "longer than" in _pace(3)


def test_an_experienced_person_is_asked_to_check_eligibility_first() -> None:
    path = learning_path(build_profile(technologies=["go"], experience="experienced"), [])
    assert any("GSoC is for students and beginners to open source" in s["step"] for s in path)
    newcomer = learning_path(build_profile(technologies=["go"], experience="new"), [])
    assert not any("Check that you can take part" in s["step"] for s in newcomer)


def test_an_interest_widens_to_narrower_subjects_but_not_to_skills() -> None:
    # A launch audit saw `repos ML4SCI` say "About Jupyter, which you care about" to
    # someone who picked "science and data": Jupyter sits under data science, as a skill.
    from git_into_gsoc.matching.ideas import wanted_domains

    wanted = wanted_domains(build_profile(interests=["data"]))
    assert "data science" in wanted
    assert "jupyter" not in wanted and "pandas" not in wanted
    assert "computer vision" in wanted_domains(build_profile(interests=["machine learning"]))
