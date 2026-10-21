"""Organization names typed by people resolve to the organization they meant, or to nothing."""

from __future__ import annotations

import pytest

from git_into_gsoc.errors import AmbiguousNameError
from git_into_gsoc.gsoc.names import core_key, resolve_name, same_org, suggest_names

CURRENT = [
    "The ns-3 Network Simulator Project",
    "R project for statistical computing",
    "Django Software Foundation",
    "MIT App Inventor",
    "Git",
    "GitLab",
    "Cuneiform Digital Library Initiative (CDLI)",
    "GNU Mailman",
    "GNU Compiler Collection (GCC)",
    "Python Software Foundation",
    "PostgreSQL",
    "rocket.chat",
    "webpack",
    "52°North Spatial Information Research GmbH",
    "Machine Learning for Science (ML4SCI)",
    "Data for the Common Good",
    "Open Data Kit",
    "TensorFlow",
    "Metasploit",
]
PAST = ["The Tor Project", "GNU Project", "GNU Radio"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Substring matches across word boundaries used to win here.
        ("R project", "R project for statistical computing"),
        ("R", "R project for statistical computing"),
        ("The R Project", "R project for statistical computing"),
        ("Tor", "The Tor Project"),
        ("Git", "Git"),
        ("git", "Git"),
        # Ordinary ways of typing a name.
        ("Django", "Django Software Foundation"),
        ("python", "Python Software Foundation"),
        ("PSF", "Python Software Foundation"),
        ("postgresql", "PostgreSQL"),
        ("tensor", "TensorFlow"),
        ("rocketchat", "rocket.chat"),
        ("Rocket.Chat", "rocket.chat"),
        ("ns3", "The ns-3 Network Simulator Project"),
        ("ns-3", "The ns-3 Network Simulator Project"),
        ("52North", "52°North Spatial Information Research GmbH"),
        ("ML4SCI", "Machine Learning for Science (ML4SCI)"),
        ("app inventor", "MIT App Inventor"),
        ("GNU Mailman Project", "GNU Mailman"),
        ("GNU", "GNU Project"),
        ("mailman", "GNU Mailman"),
    ],
)
def test_resolves_the_organization_people_mean(query: str, expected: str) -> None:
    assert resolve_name(query, CURRENT, PAST) == expected


@pytest.mark.parametrize("query", ["Go", "web", "AI", "ML", "Kubernetes", "inventor x", "Meta", ""])
def test_unknown_or_partial_words_resolve_to_nothing(query: str) -> None:
    assert resolve_name(query, CURRENT, PAST) is None


def test_a_name_shared_by_several_organizations_is_reported_not_guessed() -> None:
    with pytest.raises(AmbiguousNameError) as caught:
        resolve_name("data", CURRENT, PAST)
    assert caught.value.candidates == ["Data for the Common Good", "Open Data Kit"]
    assert "Data for the Common Good" in str(caught.value)


def test_a_common_short_form_means_the_main_project() -> None:
    assert resolve_name("postgres", [*CURRENT, "The Postgres Operator"]) == "PostgreSQL"
    assert resolve_name("Postgres Operator", [*CURRENT, "The Postgres Operator"]) == (
        "The Postgres Operator"
    )


def test_current_organizations_win_a_tie_with_past_ones() -> None:
    assert resolve_name("Radio", ["GNU Radio"], ["Radio Project Archive"]) == "GNU Radio"


def test_same_org_ignores_filler_words_but_not_real_ones() -> None:
    assert same_org("GNU Mailman", "GNU Mailman Project")
    assert same_org("Apache Software Foundation", "The Apache Software Foundation")
    assert same_org("Ceph", "Ceph Foundation")
    assert not same_org("Git", "GitLab")
    assert not same_org("Apache Software Foundation", "Apache DataFusion")
    assert core_key("The Rust Foundation") == core_key("Rust")


def test_suggestions_catch_typos_and_partial_words() -> None:
    assert suggest_names("Pyhton", CURRENT)[0] == "Python Software Foundation"
    assert "PostgreSQL" in suggest_names("postgre sql", CURRENT)
    assert suggest_names("zzzz", CURRENT) == []
