"""The pure pointer functions: mentions, path resolution, closing pull requests, fix norms, and
title words."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from git_into_gsoc.github.pointers import (
    closing_pull_request,
    extract_mentions,
    fix_norm,
    resolve_paths,
)

NOW = datetime(2026, 10, 21, tzinfo=UTC)


def _iso(seconds_ago: int) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat().replace("+00:00", "Z")


BODY = """
Running `import_tracker` on a package fails.

```
Traceback (most recent call last):
  File "/usr/lib/python3.12/site-packages/import_tracker/__main__.py", line 755, in main
    get_all_new_modules(x)
  File "/usr/lib/python3.12/runpy.py", line 88, in _run_code
```

See https://github.com/IBM/import-tracker/blob/main/import_tracker/import_tracker.py#L40
and the `_set_ending_modules` helper. Flags `-m` and `-n` do not help. Config lives in setup_tools.py.
"""


def test_extract_mentions_weights_sources() -> None:
    mentions = extract_mentions(BODY, repo="IBM/import-tracker")
    by_text = {m["text"]: m for m in mentions}
    assert by_text["import_tracker/import_tracker.py"]["kind"] == "blob_url"
    assert by_text["import_tracker/import_tracker.py"]["line"] == 40
    frame = by_text["/usr/lib/python3.12/site-packages/import_tracker/__main__.py"]
    assert frame["kind"] == "stack_frame" and frame["line"] == 755
    assert by_text["_set_ending_modules"]["kind"] in {"identifier", "backtick"}
    assert "and" not in by_text
    assert by_text["setup_tools.py"]["kind"] == "path"
    assert "-m" not in by_text and "m" not in by_text


def test_resolve_paths_exact_suffix_basename_and_drop_unknown() -> None:
    tree = [
        "import_tracker/__init__.py",
        "import_tracker/__main__.py",
        "import_tracker/import_tracker.py",
        "import_tracker/setup_tools.py",
        "tests/test_main.py",
    ]
    mentions = extract_mentions(BODY, repo="IBM/import-tracker")
    resolved = resolve_paths(mentions, tree)
    paths = [r["path"] for r in resolved]
    assert paths[0] == "import_tracker/import_tracker.py"  # blob url, highest weight
    assert "import_tracker/__main__.py" in paths
    assert "import_tracker/setup_tools.py" in paths
    assert not any("runpy" in p for p in paths)
    main_entry = next(r for r in resolved if r["path"] == "import_tracker/__main__.py")
    assert main_entry["confidence"] == "stack trace"
    assert 755 in main_entry["lines"]
    unresolved = [m["text"] for m in mentions if m["kind"] in {"identifier", "backtick"}]
    assert "_set_ending_modules" in unresolved


def test_closing_pull_request_uses_same_repo_and_close_time() -> None:
    issue = {"number": 1, "closed_at": _iso(100), "closed_by": None}
    timeline = [
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 99,
                    "repository": {"full_name": "other/repo"},
                    "pull_request": {"merged_at": _iso(100)},
                    "html_url": "https://github.com/other/repo/pull/99",
                }
            },
        },
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 42,
                    "repository": {"full_name": "acme/lib"},
                    "pull_request": {"merged_at": _iso(101)},
                    "html_url": "https://github.com/acme/lib/pull/42",
                    "created_at": _iso(3600 * 24 * 3),
                }
            },
        },
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 10,
                    "repository": {"full_name": "acme/lib"},
                    "pull_request": {"merged_at": _iso(3600 * 24 * 40)},
                    "html_url": "https://github.com/acme/lib/pull/10",
                }
            },
        },
    ]
    found = closing_pull_request(issue, timeline, repo="acme/lib")
    assert found is not None and found["number"] == 42 and found["confidence"] == "closing PR"
    older = closing_pull_request({"number": 2, "closed_at": _iso(0)}, timeline[2:], repo="acme/lib")
    assert older is not None and older["number"] == 10 and older["confidence"] == "likely fix"
    assert (
        closing_pull_request({"number": 3, "closed_at": _iso(0)}, timeline[:1], repo="acme/lib")
        is None
    )


def test_fix_norm_summarises_files_tests_and_docs() -> None:
    fixes: list[dict[str, Any]] = [
        {"files": ["lib/a.py", "lib/tests/test_a.py"]},
        {"files": ["lib/b.py", "lib/tests/test_b.py", "doc/whats_new.rst"]},
        {"files": ["README.md"]},
    ]
    norm = fix_norm(fixes)
    assert norm["sample"] == 3
    assert norm["median_files"] == 2
    assert norm["touches_tests_pct"] == 67
    assert norm["touches_docs_pct"] == 67
    assert fix_norm([]) == {"sample": 0}


def test_fix_norm_counts_common_test_folders() -> None:
    # ArduPilot keeps its tests in Tools/autotest; pointers said "0% touch tests".
    fixes = [
        {"files": ["ArduSub/mode.cpp", "Tools/autotest/ardusub.py"]},
        {"files": ["web/src/app.ts", "web/src/app.spec.ts"]},
        {"files": ["src/latest/notes.md"]},
    ]
    norm = fix_norm(fixes)
    assert norm["touches_tests_pct"] == 67  # autotest and .spec.ts count; "latest" does not


def test_title_keywords_pick_distinctive_words() -> None:
    from git_into_gsoc.github.pointers import title_keywords

    assert title_keywords("Two undo/redo methods do not join up") == ["undo", "redo"]
    assert title_keywords("Add version to Docs site") == ["docs", "site"]
    assert title_keywords("Fix it") == []
    # sympy/sympy#30671: "find, bugs" searched README and a Fortran parser.
    title = "Find bugs in the rewrite of SymPy's assumption system"
    assert title_keywords(title, exclude=("sympy", "sympy")) == ["assumption"]


def test_rank_similar_prefers_shared_words_and_says_when_none_are_shared() -> None:
    from git_into_gsoc.github.pointers import rank_similar

    items = [
        {"number": 1, "title": "Add version to Docs site"},
        {"number": 2, "title": "Redo button greyed out after undo"},
        {"number": 3, "title": "Configurable OAuth frontend URL"},
    ]
    ranked, shared = rank_similar("Two undo/redo methods do not join up", items, limit=2)
    assert shared is True
    assert ranked[0]["number"] == 2
    unrelated, shared = rank_similar("Translate to Farsi", items, limit=2)
    assert shared is False
    assert [i["number"] for i in unrelated] == [1, 2]  # newest first, as GitHub sent them


def test_a_name_in_the_issue_matches_a_file_name_without_code_search() -> None:
    # kornia/kornia#3279, "distance_transform bug", was fixed in
    # kornia/contrib/distance_transform.py. Without a token there is no code search,
    # so the name was dropped and the person got no pointer at all.
    tree = [
        "kornia/contrib/distance_transform.py",
        "kornia/contrib/__init__.py",
        "tests/contrib/test_distance_transform.py",
        "docs/source/contrib.rst",
    ]
    mentions = extract_mentions("distance_transform bug\nThe output is wrong for 3D input.")
    found = resolve_paths(mentions, tree)
    assert [f["path"] for f in found][:1] == ["kornia/contrib/distance_transform.py"]
    assert found[0]["confidence"] == "file name match"
    # A short or common name does not match a pile of files.
    assert resolve_paths(extract_mentions("`setup` fails"), ["a/setup.py", "b/setup.py"]) == []


def test_code_files_come_before_changelogs_and_docs() -> None:
    from git_into_gsoc.github.pointers import code_first

    # Code search for kornia's distance_transform: the real file, then changelog entries.
    found = [
        "changelog.d/6045.fixed.md",
        "kornia/contrib/distance_transform.py",
        "CONTRIBUTING.md",
        "docs/source/contrib.rst",
        "kornia/contrib/__init__.py",
    ]
    assert code_first(found)[:2] == [
        "kornia/contrib/distance_transform.py",
        "kornia/contrib/__init__.py",
    ]


def test_title_words_that_spell_a_code_file_point_at_it() -> None:
    from git_into_gsoc.github.pointers import title_file_matches

    # Without a token there is no code search; a title that spells a file name still
    # points somewhere useful (openfoodfacts-server#10825, "knowledge panel").
    tree = [
        "lib/ProductOpener/KnowledgePanels.pm",
        "tests/unit/knowledge_panels.t",
        "docs/api/explain-knowledge-panels.md",
        "lib/ProductOpener/Products.pm",
    ]
    found = title_file_matches("Tweak the report product knowledge panel icon", tree)
    paths = [f["path"] for f in found]
    assert paths[0] == "lib/ProductOpener/KnowledgePanels.pm"
    assert "docs/api/explain-knowledge-panels.md" not in paths  # docs are not a starting point
    assert title_file_matches("Fix the button", tree) == []
