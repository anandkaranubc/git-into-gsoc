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
    assert ranked[0].fit == "strong"
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
    edu = [_org(f"School {i}", tech=["python"], topics=["education"]) for i in range(5)]
    games = _org("Game Shop", tech=["python"], topics=["games"], num_projects_latest=1)
    names = [
        m.org.name
        for m in _rank([*edu, games], technologies=["python"], interests=["education", "games"])
    ]
    assert "Game Shop" in names[:3]


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
