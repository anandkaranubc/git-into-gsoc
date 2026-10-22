"""The skill and domain vocabulary: what people and organizations mean by their words."""

from __future__ import annotations

import pytest

from git_into_gsoc.matching.concepts import (
    CONCEPTS,
    find_concepts,
    find_tag_concepts,
    resolve,
)
from git_into_gsoc.matching.profile import (
    build_profile,
    effective_experience,
    experience_from_merged,
)


@pytest.mark.parametrize(
    ("typed", "concept"),
    [
        ("healthcare", "health"),
        ("web dev", "web"),
        ("AI", "machine learning"),
        ("LLMs", "large language models"),
        ("node.js", "nodejs"),
        ("Golang", "go"),
        ("k8s", "kubernetes"),
        ("ci/cd", "devops"),
        ("maps", "geospatial"),
        ("music", "audio"),
        ("command line tools", "developer tools"),
        ("genomics", "bioinformatics"),
        ("phoenix", "phoenix"),
        ("nltk", "nltk"),
        ("leaflet", "leaflet"),
        ("game moding", "games"),
        ("web backends", "backend"),
        # From accepted 2026 projects (dev) the ranker missed.
        ("linting", "developer tools"),
        ("code quality", "developer tools"),
        ("mailing lists", "communication"),
        ("hardware design", "embedded"),
        # A common beginner's interest that read as data science or as nothing.
        ("data structures", "algorithms"),
        ("competitive programming", "algorithms"),
    ],
)
def test_peoples_words_reach_the_concept_they_mean(typed: str, concept: str) -> None:
    assert concept in resolve(typed).concepts


def test_a_compound_skill_names_both_parts() -> None:
    assert set(resolve("c/c++").concepts) == {"c", "c++"}


def test_misspellings_are_read_and_reported() -> None:
    known = resolve("pyhton")
    assert known.concepts == ("python",) and known.corrected_from == "python"
    close = resolve("data vizualisation")
    assert close.concepts == ("data visualization",) and close.corrected_from
    assert resolve("data viz").concepts == ("data visualization",)
    assert resolve("python").corrected_from is None
    assert resolve("zzqx").concepts == ()


def test_ambiguous_words_are_not_trusted_in_free_text() -> None:
    text = (
        "Set up a development environment, fix the genome assembly parser, design the API, "
        "react to events, and read about game theory and angular momentum."
    )
    found = find_concepts(text)
    for wrong in ("climate", "assembly", "design", "react", "games", "angular", "compilers"):
        assert wrong not in found, wrong
    assert "mathematics" in found  # "game theory" is mathematics, not games
    # The usual capital letter is enough: "Written in Go and React".
    assert {"go", "react"} <= set(find_concepts("Written in Go and React"))


def test_a_generic_word_counts_as_a_whole_tag_but_not_inside_a_longer_one() -> None:
    assert "systems programming" not in find_tag_concepts("systems management")
    assert "systems programming" in find_tag_concepts("performance")
    assert "science" in find_tag_concepts("science and medicine")
    assert "health" not in find_tag_concepts("science and medicine")
    assert "health" in find_tag_concepts("heathcare")  # an organization's own typo


def test_every_link_points_at_a_known_concept() -> None:
    for concept in CONCEPTS.values():
        for other in (*concept.broader, *concept.related):
            assert other in CONCEPTS, (concept.key, other)


def test_a_domain_typed_as_a_skill_becomes_an_interest() -> None:
    person = build_profile(technologies=["python", "robotics"], interests=["rust"])
    assert [w.concepts for w in person.skills] == [("python",), ("rust",)]
    assert [w.concepts for w in person.interests] == [("robotics",)]


def test_skills_imply_interests_only_when_none_are_given_explicitly() -> None:
    person = build_profile(technologies=["pytorch"])
    assert ("machine learning",) in [w.concepts for w in person.implied_interests]
    stated = build_profile(technologies=["pytorch"], interests=["machine learning"])
    assert stated.implied_interests == []


def test_profile_reads_levels_and_hours_and_drops_nonsense() -> None:
    person = build_profile(technologies=["a little python"], experience="NEW", hours_per_week=8)
    assert person.skills[0].raw == "python" and person.experience == "new"
    assert person.hours_per_week == 8
    assert build_profile(experience="guru", hours_per_week=0).experience is None


def test_experience_comes_from_the_person_first_then_merged_pull_requests() -> None:
    assert experience_from_merged(0) == "new"
    assert experience_from_merged(3) == "some"
    assert experience_from_merged(25) == "experienced"
    assert experience_from_merged(None) is None
    level, source = effective_experience({"merged_prs_elsewhere": 1})
    assert level == "some" and source and "1 merged pull request in" in source
    assert effective_experience({"experience": "new", "merged_prs_elsewhere": 40}) == (
        "new",
        "you said so",
    )
    assert effective_experience({}) == (None, None)


def test_slashed_tags_name_every_part() -> None:
    assert {"c", "c++"} <= set(find_tag_concepts("c/c++"))
    assert {"c", "c++"} <= set(find_tag_concepts("C\\C++"))
    assert {"c", "rust", "go"} <= set(find_tag_concepts("c/rust/go"))
    assert {"dart", "flutter"} <= set(find_tag_concepts("dart/flutter"))


def test_in_a_phrase_the_specific_word_wins_over_an_ambiguous_one() -> None:
    # "realtime chat" was read as embedded systems plus chat.
    assert resolve("realtime chat").concepts == ("communication",)
    assert resolve("realtime").concepts == ("embedded",)
    assert resolve("real-time systems").concepts == ("embedded",)
    # A quantum chemistry tag is chemistry, not quantum computing, and routing
    # protocols are networking, not maps.
    assert find_tag_concepts("quantum chemistry") == {"chemistry": 1}
    assert resolve("routing protocols").concepts == ("networking",)
    assert resolve("map routing").concepts == ("geospatial",)


def test_skills_come_down_to_the_languages_github_searches() -> None:
    from git_into_gsoc.matching.profile import languages_of

    assert languages_of(build_profile(technologies=["django", "react"])) == ["python", "javascript"]
    assert languages_of(build_profile(technologies=["flutter"])) == ["dart"]
    assert languages_of(build_profile(technologies=["c#", "unity"])) == ["csharp"]
    assert languages_of(build_profile(technologies=["markdown", "git"])) == []


def test_a_search_can_cover_several_languages_and_their_relatives() -> None:
    from git_into_gsoc.github.search import language_group

    assert language_group("python") == "language:python"
    assert language_group(["python", "javascript"]) == (
        "(language:python OR language:javascript OR language:typescript)"
    )


def test_competency_words_count_when_typed_but_not_in_an_ideas_page() -> None:
    # "Write code with good code quality" asks for a habit, not a subject (see #292).
    assert find_concepts("Write good code quality and fix linting issues") == {}
    # 115 of 183 organizations list a mailing list as a contact channel: "ask on our
    # mailing list" in an ideas page is how to reach them, not what they work on.
    assert find_concepts("Ask on our mailing list; we run style checkers in CI") == {}
    assert find_tag_concepts("mailing lists") == {"communication": 1}
    assert find_tag_concepts("code quality") == {"developer tools": 1}
    assert resolve("hardware design").concepts == ("embedded",)


def test_misspelled_algorithm_words_reach_algorithms_through_the_fuzzy_path() -> None:
    # dev3 (common beginners): "data structers" read as data science.
    for typed, meant in [
        ("data structers", "data structures"),
        ("algoritms", "algorithms"),
        ("competitive programing", "competitive programming"),
    ]:
        found = resolve(typed)
        assert found.concepts == ("algorithms",) and found.corrected_from == meant
