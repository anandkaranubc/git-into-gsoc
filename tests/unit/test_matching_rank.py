"""Organization ranking: relevance decides, evidence explains, tie-breakers stay small."""

from __future__ import annotations

from typing import Any

from git_into_gsoc.matching.orgs import build_org_profile
from git_into_gsoc.matching.profile import build_profile
from git_into_gsoc.matching.rank import OrgIndex, match_term
from git_into_gsoc.models import OrgSummary


def _org(name: str, *, tech: list[str], topics: list[str], **extra: Any) -> OrgSummary:
    defaults: dict[str, Any] = {
        "slug": name.lower().replace(" ", "-"),
        "description": "",
        "years_active": [2022, 2023, 2024, 2025, 2026],
        "num_projects_latest": 5,
        "latest_year": 2026,
        "projects_by_year": {2024: 5, 2025: 5, 2026: 5},
        "guide_url": "https://example.org/guide",
    }
    return OrgSummary(name=name, technologies=tech, topics=topics, **(defaults | extra))


ASTRO = _org("Star Lab", tech=["python", "numpy"], topics=["astronomy"])
SECURITY = _org("Shield", tech=["python", "c"], topics=["security"])
PHYSICS = _org("Particle Group", tech=["c++", "python"], topics=["physics"])
CLINIC = _org("Clinic Tools", tech=["javascript", "react"], topics=["electronic medical records"])
KOTLIN = _org("Pocket Apps", tech=["kotlin"], topics=["mobile"])
GTK = _org("Desktop Club", tech=["c", "gtk"], topics=["desktop"])
CPP = _org("Engine Works", tech=["c++"], topics=["graphics"])
ORGS = [ASTRO, SECURITY, PHYSICS, CLINIC, KOTLIN, GTK, CPP]


def _rank(
    orgs: list[OrgSummary] = ORGS,
    signals: dict[str, Any] | None = None,
    *,
    query: str = "",
    category: str = "",
    **person: Any,
):
    index = OrgIndex.build(orgs, signals=signals, reference_year=2026)
    return index.rank(build_profile(**person), query=query, category=category)


def test_interest_decides_order_among_orgs_that_share_a_language() -> None:
    names = [m.org.name for m in _rank(technologies=["python"], interests=["astronomy"])]
    assert names[0] == "Star Lab"
    # Physics is next to astronomy, so it ranks above security, which only shares Python.
    assert names.index("Particle Group") < names.index("Shield")


def test_domain_words_reach_tags_written_differently() -> None:
    ranked = _rank(interests=["healthcare"])
    assert ranked[0].org.name == "Clinic Tools"
    # One tag is a good fit; a strong one needs a second kind of evidence to agree.
    assert ranked[0].fit == "good"
    index = OrgIndex.build(
        [CLINIC], descriptions={"Clinic Tools": "Software for hospitals."}, reference_year=2026
    )
    assert index.rank(build_profile(interests=["healthcare"]))[0].fit == "strong"
    assert any("electronic medical records" in line for line in ranked[0].evidence())


def test_every_reason_names_its_source() -> None:
    top = _rank(technologies=["python"], interests=["astronomy"])[0]
    lines = top.evidence()
    assert lines and all("official GSoC listing" in line for line in lines)
    assert "Topic: Astronomy and space" in top.reasons()
    assert "Uses Python" in top.reasons()


def test_a_skill_only_search_lists_orgs_that_use_it_not_neighbours() -> None:
    names = {m.org.name for m in _rank(technologies=["c"])}
    assert names == {"Shield", "Desktop Club"}  # never the C++-only Engine Works


def test_rare_skills_say_more_than_common_ones() -> None:
    orgs = [_org(f"Py {i}", tech=["python"], topics=["web"]) for i in range(6)] + [KOTLIN]
    ranked = _rank(orgs, technologies=["python", "kotlin"])
    assert ranked[0].org.name == "Pocket Apps"


def test_skills_are_alternatives_so_one_usable_skill_is_enough() -> None:
    ranked = _rank(technologies=["python", "kotlin"], interests=["astronomy"])
    assert ranked[0].org.name == "Star Lab"  # uses Python only, and that is fine
    assert ranked[0].skill_fit is not None and ranked[0].skill_fit >= 0.5


def test_unknown_words_still_match_literally() -> None:
    org = _org("Odd One", tech=["python"], topics=["birdsong"])
    ranked = _rank([org, ASTRO], interests=["birdsong"])
    assert [m.org.name for m in ranked] == ["Odd One"]
    assert ranked[0].interests[0].how == "word"


def test_corroborated_evidence_beats_a_single_mention() -> None:
    central = _org("Web Core", tech=["javascript"], topics=["web"])
    side = _org("Bio Net", tech=["javascript"], topics=["web", "biology"])
    signals = {
        "year": 2026,
        "organizations": {
            "web-core": {
                "ideas": {"count": 4, "skills": {"web": 3}, "mentions": {"web": 4}},
                "github": {
                    "active_repos": 6,
                    "languages": {"JavaScript": 5},
                    "concepts": {"web": 4},
                },
            }
        },
    }
    ranked = _rank([side, central], signals=signals, technologies=["javascript"], interests=["web"])
    assert ranked[0].org.name == "Web Core"


def test_new_contributors_are_warned_about_hard_only_idea_pages() -> None:
    hard = _org("Deep End", tech=["c"], topics=["operating systems"])
    easy = _org("Shallow End", tech=["c"], topics=["operating systems"])
    signals = {
        "year": 2026,
        "organizations": {
            "deep-end": {"ideas": {"count": 5, "difficulty": {"hard": 5}}},
            "shallow-end": {"ideas": {"count": 5, "difficulty": {"easy": 3, "medium": 2}}},
        },
    }
    ranked = _rank(
        [hard, easy], signals=signals, technologies=["c"], interests=["kernel"], experience="new"
    )
    assert [m.org.name for m in ranked] == ["Shallow End", "Deep End"]
    assert any("are hard" in c for c in ranked[1].caveats)
    assert any("3 easy, 2 medium" in r for r in ranked[0].readiness)


def test_sizes_that_cannot_fit_the_hours_are_named() -> None:
    org = _org("Big Ideas", tech=["python"], topics=["astronomy"], slug="big-ideas")
    signals = {
        "year": 2026,
        "organizations": {"big-ideas": {"ideas": {"count": 3, "size": {"large": 3}}}},
    }
    ranked = _rank([org], signals=signals, interests=["astronomy"], hours_per_week=5)
    assert any("more than 22 weeks" in c for c in ranked[0].caveats)


def test_tie_breakers_never_overturn_a_clearly_better_match() -> None:
    veteran = _org(
        "Veteran",
        tech=["python"],
        topics=["security"],
        years_active=list(range(2010, 2027)),
        num_projects_latest=40,
    )
    newcomer = _org(
        "Fresh Stars",
        tech=["python"],
        topics=["astronomy"],
        years_active=[2026],
        num_projects_latest=1,
        guide_url=None,
    )
    ranked = _rank([veteran, newcomer], technologies=["python"], interests=["astronomy"])
    assert ranked[0].org.name == "Fresh Stars"


def test_several_interests_each_show_up_near_the_top() -> None:
    edu = [_org(f"Org {i}", tech=["python"], topics=["education"]) for i in range(5)]
    games = _org("Fun Shop", tech=["python"], topics=["games"], num_projects_latest=1)
    names = [
        m.org.name
        for m in _rank([*edu, games], technologies=["python"], interests=["education", "games"])
    ]
    assert "Fun Shop" in names[:3]


def test_query_matches_names_and_words_and_category_filters() -> None:
    by_name = _rank(query="star")
    assert by_name[0].org.name == "Star Lab" and "Name matches 'star'" in by_name[0].reasons()
    assert _rank(query="nonexistentword") == []
    science = _org("Lab", tech=["python"], topics=[], category="Science and medicine")
    assert [m.org.name for m in _rank([science, KOTLIN], category="science")] == ["Lab"]


def test_match_term_explains_a_match_through_a_neighbour() -> None:
    profile = build_org_profile(PHYSICS)
    term = match_term(profile, build_profile(interests=["astronomy"]).interests[0])
    assert term.how == "related" and term.via == "Physics"
    assert 0 < term.strength < 0.5


def test_a_query_that_names_a_skill_searches_that_skill() -> None:
    # `orgs --query go` and `--query js` returned nothing when the query was read
    # only as a plain word of three letters or more.
    go = _org("Gopher Club", tech=["golang"], topics=["cloud"])
    js = _org("Script Shop", tech=["javascript"], topics=["web"])
    assert [m.org.name for m in _rank([go, js, ASTRO], query="go")] == ["Gopher Club"]
    assert [m.org.name for m in _rank([go, js, ASTRO], query="js")] == ["Script Shop"]
    assert [m.org.name for m in _rank([go, js, ASTRO], query="pyhton")] == ["Star Lab"]


def test_a_slashed_tag_keeps_its_short_words() -> None:
    both = _org("Compiler Co", tech=["c/c++"], topics=["compilers"])
    mixed = _org("Poly", tech=["C/Rust/Go"], topics=["cloud"])
    names = {m.org.name for m in _rank([both, mixed, CPP], technologies=["c"])}
    assert names == {"Compiler Co", "Poly"}


def test_no_fit_is_claimed_when_nothing_personal_was_given() -> None:
    assert all(m.fit is None for m in _rank())
    science = _org("Lab", tech=["python"], topics=[], category="Science and medicine")
    assert [m.fit for m in _rank([science], category="science")] == [None]
    assert _rank(query="star")[0].fit == "strong"


def test_a_broad_organization_says_less_about_each_skill_than_a_focused_one() -> None:
    focused = _org("Rust Tools", tech=["rust"], topics=["developer tools"])
    many = ["rust", "python", "go", "java", "c++", "ruby", "javascript", "php", "lua"]
    polyglot = _org("Poly Runtime", tech=many, topics=["developer tools"])
    others = [_org(f"Small {i}", tech=["python"], topics=["web"]) for i in range(5)]
    ranked = _rank(
        [polyglot, focused, *others], technologies=["rust"], interests=["developer tools"]
    )
    assert [m.org.name for m in ranked[:2]] == ["Rust Tools", "Poly Runtime"]


def test_vague_words_get_narrower_suggestions_with_counts() -> None:
    ai = [_org(f"AI {i}", tech=["python"], topics=["machine learning"]) for i in range(4)]
    vision = [_org(f"Vision {i}", tech=["python"], topics=["computer vision"]) for i in range(3)]
    llm = [_org(f"LLM {i}", tech=["python"], topics=["llm"]) for i in range(2)]
    index = OrgIndex.build([*ai, *vision, *llm], reference_year=2026)
    tips = index.sharpen(build_profile(interests=["ai"]), broad=5)
    assert tips[0]["word"] == "ai" and tips[0]["matches"] == 9
    assert tips[0]["suggest"] == [("Computer vision", 3), ("LLMs and AI agents", 2)]
    skill_tips = index.sharpen(build_profile(technologies=["python"]), broad=5)
    assert skill_tips[0]["kind"] == "skill"
    assert ("Machine learning and AI", 9) in skill_tips[0]["suggest"]
    assert index.sharpen(build_profile(interests=["computer vision"]), broad=5) == []


def test_a_skill_never_matches_through_a_subject_or_a_neighbouring_skill() -> None:
    # Live review: "Skill Phoenix (through Backend and APIs): Django" and "Skill Assembly
    # (through C)" claimed matches that were not there.
    django = _org("Py Web", tech=["django"], topics=["web"])
    c_only = _org("C House", tech=["c"], topics=["operating systems"])
    assert _rank([django], technologies=["phoenix"]) == []
    assert _rank([c_only], technologies=["assembly"]) == []


def test_a_near_topic_match_says_it_is_not_the_topic() -> None:
    ranked = _rank([PHYSICS], technologies=["python"], interests=["astronomy"])
    line = next(e for e in ranked[0].evidence() if e.startswith("Topic Astronomy"))
    assert "not named; the nearest is Physics" in line


def test_an_org_named_after_the_skill_is_its_home_but_not_for_newcomers() -> None:
    home = _org("The Rust Foundation", tech=["rust"], topics=["compilers"])
    other = _org("Ferrous Tools", tech=["rust"], topics=["compilers"], num_projects_latest=20)
    ranked = _rank([other, home], technologies=["rust"], experience="some")
    assert ranked[0].org.name == "The Rust Foundation"
    assert "Named after Rust" in ranked[0].reasons()
    new = _rank([other, home], technologies=["rust"], experience="new")
    assert "Named after Rust" not in new[0].reasons() + new[1].reasons()
    # "game theory" in a name is mathematics, not games.
    gambit = _org("Gambit: computation in game theory", tech=["c++"], topics=["games"])
    assert not any(
        r.startswith("Named after") for r in _rank([gambit], interests=["games"])[0].reasons()
    )


def test_a_blocking_caveat_keeps_a_fit_from_being_strong() -> None:
    org = _org("Fortran Hub", tech=["python", "fortran"], topics=["scientific computing"])
    signals = {
        "year": 2026,
        "organizations": {"fortran-hub": {"ideas": {"count": 4, "skills": {"fortran": 4}}}},
    }
    ranked = _rank(
        [org], signals=signals, technologies=["python"], interests=["scientific computing"]
    )
    assert ranked[0].fit == "good"
    assert any(c.startswith("Most of its ideas need Fortran") for c in ranked[0].caveats)


def test_a_skill_no_organization_uses_is_said_plainly() -> None:
    index = OrgIndex.build(ORGS, reference_year=2026)
    notes = index.coverage(build_profile(technologies=["elixir", "python"]))
    assert len(notes) == 1 and notes[0].startswith("No 2026 GSoC organization uses Elixir")


def test_an_org_the_monthly_check_saw_sitting_out_moves_down_wherever_it_ranks() -> None:
    # A live run listed Learning Unlimited sixth with no warning: only the top three
    # were checked at query time. The monthly evidence now carries the statement.
    out = _org("Sits Out", tech=["html", "css"], topics=["education"], slug="sits-out")
    stays = _org("Stays", tech=["html"], topics=["education"], slug="stays")
    said = {
        "status": "not_taking_part",
        "url": "https://x/wiki",
        "year": 2027,
        "checked": "2026-10-21",
    }
    signals = {"year": 2026, "organizations": {"sits-out": {"participation": said}}}
    ranked = _rank(
        [out, stays], signals=signals, technologies=["html", "css"], interests=["education"]
    )
    assert [m.org.name for m in ranked] == ["Stays", "Sits Out"]
    assert (
        ranked[1]
        .caveats[0]
        .startswith("Said it will not take part in GSoC 2027 (checked 2026-10-21)")
    )
    assert ranked[1].participation == {
        "status": "not_taking_part",
        "url": "https://x/wiki",
        "checked": "2026-10-21",
    }


def test_evidence_fractions_never_exceed_their_base_and_poor_splits_are_said() -> None:
    # Live review: "named in 11 of 2 2026 ideas" when headings were dropped from the count.
    org = _org("Split Page", tech=["python"], topics=["education"], slug="split-page")
    signals = {
        "year": 2026,
        "organizations": {
            "split-page": {
                "ideas": {"url": "https://x", "count": 2, "blocks": 14, "mentions": {"git": 11}}
            }
        },
    }
    ranked = _rank([org], signals=signals, technologies=["git"], interests=["education"])
    lines = " ".join(ranked[0].evidence())
    assert "named in 11 of 14 parts of its 2026 ideas page" in lines
    assert not any("idea on its" in r or "ideas on its" in r for r in ranked[0].readiness)
    assert any("could not pick out ideas" in c for c in ranked[0].caveats)


def test_an_unnamed_interest_is_at_most_a_partial_fit_and_main_language_is_named() -> None:
    rusty = _org("Rusty Robots", tech=["rust", "python"], topics=["physics"], slug="rusty-robots")
    signals = {
        "year": 2026,
        "organizations": {
            "rusty-robots": {"github": {"active_repos": 10, "languages": {"Rust": 7, "Python": 3}}}
        },
    }
    ranked = _rank([rusty], signals=signals, technologies=["python"], interests=["astronomy"])
    assert ranked[0].fit == "partial"  # astronomy is only near (physics), never named
    assert any(c.startswith("Its code is mostly Rust") for c in ranked[0].caveats)


def test_hyphenated_tags_keep_spellings_that_need_the_hyphen() -> None:
    # The R project tags itself "r-project"; reading the tag only as "r project" lost R.
    stats = _org("Stats Home", tech=["c", "r-project"], topics=["statistics"])
    other = _org("Plot Lab", tech=["javascript"], topics=["statistics", "visualization"])
    ranked = _rank([stats, other], technologies=["r"], interests=["statistics"])
    assert ranked[0].org.name == "Stats Home"
    assert ranked[0].skills[0].how == "direct"
    assert "r-project" in " ".join(ranked[0].skills[0].evidence)


def test_supply_chain_security_is_its_own_subject_under_security() -> None:
    factory = _org("Build Factory", tech=["go"], topics=["SLSA", "supplychain"])
    malware = _org("Malware Watch", tech=["go"], topics=["malware analysis"])
    ranked = _rank([malware, factory], technologies=["go"], interests=["sboms and code signing"])
    assert ranked[0].org.name == "Build Factory"
    watch = next(m for m in ranked if m.org.name == "Malware Watch")
    assert watch.interests[0].how == "broader"  # security in general, not this subject


def test_a_phrase_with_a_common_and_a_rare_subject_leans_on_the_rare_one() -> None:
    sound = _org("Sound Lab", tech=["python"], topics=["audio"])
    models = [
        _org(f"Model Lab {n}", tech=["python"], topics=["machine learning"]) for n in range(6)
    ]
    ranked = _rank([*models, sound], technologies=["python"], interests=["audio machine learning"])
    # Machine learning is everywhere; audio is what this person asked for.
    assert ranked[0].org.name == "Sound Lab"
    model = next(m for m in ranked if m.org.name.startswith("Model Lab"))
    assert model.interests[0].strength < 0.5 < ranked[0].interests[0].strength


def test_a_broad_word_in_a_name_is_not_what_an_organization_is_named_after() -> None:
    perfusion = _org("Open Science Imaging Group", tech=["python"], topics=["science"])
    ranked = _rank([perfusion], technologies=["python"], interests=["science"], experience="some")
    assert not any(r.startswith("Named after") for r in ranked[0].reasons())


def test_readiness_says_whether_an_organization_labels_first_tasks_on_github() -> None:
    quiet = _org("Lab Without Labels", tech=["python"], topics=["physics"])
    busy = _org("Labelling Lab", tech=["python"], topics=["physics"])

    def github(labelled: int) -> dict[str, Any]:
        return {"active_repos": 8, "languages": {"Python": 8}, "beginner_issues_year": labelled}

    signals = {
        "year": 2026,
        "organizations": {
            "lab-without-labels": {"github": github(0)},
            "labelling-lab": {"github": github(14)},
        },
    }
    ranked = {m.org.name: m for m in _rank([quiet, busy], signals=signals, interests=["physics"])}
    # Zero is never stated: the project may use its own label ("Difficulty-easy").
    assert not any("beginner label" in line for line in ranked["Lab Without Labels"].readiness)
    line = next(x for x in ranked["Labelling Lab"].readiness if "beginner label" in x)
    # Said as a habit, never as issues open now.
    assert line.startswith(
        "14 GitHub issues with a common beginner label were opened in the past year"
    )
    assert "open or since closed" in line and "issues --org" in line
    # Evidence only: the two still tie on everything that ranks them.
    assert ranked["Lab Without Labels"].score == ranked["Labelling Lab"].score


def test_a_reported_statement_is_a_quoted_caveat_and_leaves_the_score() -> None:
    org = _org("Symbolic Lab", tech=["python"], topics=["mathematics"])
    said = {
        "status": "reported",
        "year": 2027,
        "url": "https://github.com/lab/lab/issues/7",
        "quote": "we will not participate in GSoC this year",
        "date": "2026-10-04",
        "by_maintainer": False,
        "checked": "2026-10-22",
    }
    plain = _rank([org], interests=["mathematics"])[0]
    signals = {"year": 2026, "organizations": {"symbolic-lab": {"participation": said}}}
    reported = _rank([org], signals=signals, interests=["mathematics"])[0]
    caveat = next(c for c in reported.caveats if "wrote in its tracker" in c)
    assert "someone GitHub does not list as a maintainer" in caveat and "2026-10-04" in caveat
    assert "Not an official statement about GSoC 2027" in caveat
    assert reported.score == plain.score


def test_most_ideas_needing_an_unlisted_skill_is_a_caveat_not_a_cost() -> None:
    php = _org("Judge Site", tech=["javascript", "php"], topics=["education"])
    ideas = {"count": 6, "skills": {"php": 5, "javascript": 1}}
    signals = {"year": 2026, "organizations": {"judge-site": {"ideas": ideas}}}
    judge = _rank([php], signals=signals, technologies=["javascript"], interests=["education"])[0]
    assert any("Most of its ideas need PHP" in c for c in judge.caveats)


def test_one_or_two_beginner_issues_in_a_year_are_not_shown() -> None:
    lab = _org("Small Lab", tech=["python"], topics=["physics"])
    signals = {
        "year": 2026,
        "organizations": {
            "small-lab": {
                "github": {"active_repos": 8, "languages": {"Python": 8}, "beginner_issues_year": 2}
            }
        },
    }
    ranked = _rank([lab], signals=signals, interests=["physics"])
    assert not any("beginner label" in line for line in ranked[0].readiness)


def test_a_narrowing_word_favours_the_organization_that_names_it() -> None:
    person = build_profile(interests=["database internals", "storage engines"])
    assert person.interests[0].qualifiers == ("internal", "storage", "engine")
    tables = _org("Tables Inc", tech=["c++"], topics=["databases"], description="A database.")
    engine = _org(
        "Engine Room", tech=["c++"], topics=["databases"], description="A storage engine."
    )
    ranked = _rank([*ORGS, tables, engine], interests=["database internals", "storage engines"])
    assert [m.org.name for m in ranked[:2]] == ["Engine Room", "Tables Inc"]
    assert "names 'storage' in its listing or ideas" in ranked[0].evidence()[0]


def test_words_that_spell_the_subject_or_say_nothing_do_not_narrow_it() -> None:
    person = build_profile(interests=["front end", "real-time operating systems", "web apps"])
    assert [w.qualifiers for w in person.interests] == [(), ("real-time",), ()]


def test_a_language_family_counts_together_and_sites_are_not_the_code() -> None:
    from git_into_gsoc.matching.rank import _main_language

    org = _org("Contracts", tech=["python"], topics=["natural language processing"])
    person = build_profile(technologies=["python"], interests=["natural language processing"])

    def caveat(languages: dict[str, int], active: int) -> str | None:
        signals = {"github": {"active_repos": active, "languages": languages}}
        return _main_language(build_org_profile(org, signals=signals), person)

    # 3 TypeScript and 2 JavaScript of 9: neither alone is 40%, together they are.
    said = caveat({"TypeScript": 3, "JavaScript": 2, "Python": 1, "HTML": 3}, 9)
    assert said and said.startswith("Its code is mostly TypeScript and JavaScript")
    # Documentation sites in HTML are not what contributors write.
    assert caveat({"HTML": 5, "Python": 4}, 9) is None
    # A TypeScript developer knows the family.
    ts = build_profile(technologies=["typescript"], interests=["natural language processing"])
    signals = {"github": {"active_repos": 9, "languages": {"TypeScript": 3, "JavaScript": 2}}}
    assert _main_language(build_org_profile(org, signals=signals), ts) is None
