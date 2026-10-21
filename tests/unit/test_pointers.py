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
