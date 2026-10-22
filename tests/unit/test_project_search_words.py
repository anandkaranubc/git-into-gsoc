"""Searching past projects finds a word in its singular and plural forms."""

from __future__ import annotations

from git_into_gsoc.gsoc.client import _mentions_any, _word_forms


def test_singular_and_plural_find_each_other() -> None:
    # `projects "polynomial" --org SymPy` (2026-10-22) missed the two newest SymPy
    # projects, "FLINT-Backed Multivariate Polynomials in SymPy" and "Enhancement of gcd
    # for polynomials", while "polynomials" missed "Polynomial functionality".
    assert _mentions_any("FLINT-Backed Multivariate Polynomials in SymPy", "polynomial")
    assert _mentions_any("Adding to SymEngine's Polynomial functionality", "polynomials")
    assert _mentions_any("Better plotting libraries", "library")
    assert _mentions_any("A new graph library", "libraries")
    assert _mentions_any("Faster index matches", "match")


def test_short_words_and_acronyms_stay_exact() -> None:
    assert _word_forms("gpu") == {"gpu"}
    assert _word_forms("c++") == {"c++"}
    # Still whole words: "classes" finds "class", not "classification".
    assert not _mentions_any("Image classification models", "classes")


def test_words_that_only_look_plural_do_not_lose_their_s() -> None:
    # A 4+ letter word ending in "s" is not always a plural of a shorter word.
    assert _word_forms("class") == {"class", "classes"}
    assert _word_forms("bus") == {"bus"}
    assert _word_forms("series") == {"series"}
    assert _word_forms("status") == {"status", "statuses"}
    assert not _mentions_any("A new graph library", "news")
    assert _mentions_any("Statistical analyses of survey data", "analysis")
    assert _mentions_any("Faster analysis of large graphs", "analyses")


def test_es_plurals_find_words_that_end_in_e() -> None:
    assert _mentions_any("A faster database layer", "databases")
    assert _mentions_any("Smarter cache invalidation", "caches")
    assert _mentions_any("Recommend a movie", "movies")
    assert _mentions_any("Merge sorted boxes", "box") is False  # three letters stay exact
    assert _mentions_any("Smarter caching for classes", "class")
