"""The `pointers` command end to end, with and without code search."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from typer.testing import CliRunner

from git_into_gsoc.cli import app
from git_into_gsoc.service import GSoCToolkit

runner = CliRunner()
API = "https://api.github.com/repos/acme/lib"
NOW = datetime.now(UTC)


def _iso(seconds_ago: int) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat().replace("+00:00", "Z")


def _mock(router: respx.MockRouter) -> None:
    router.get(f"{API}/issues/12").mock(
        return_value=httpx.Response(
            200,
            json={
                "number": 12,
                "title": "Crash in parser on empty input",
                "html_url": "https://github.com/acme/lib/issues/12",
                "state": "open",
                "labels": [{"name": "good first issue"}],
                "body": 'Traceback:\n  File "/x/site-packages/lib/parser.py", line 40, in parse\nSee `tokenize_line` too.',
            },
        )
    )
    router.get(API).mock(
        return_value=httpx.Response(200, json={"full_name": "acme/lib", "default_branch": "main"})
    )
    router.get(f"{API}/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "feedface0001",
                "tree": [
                    {"path": "lib/parser.py", "type": "blob"},
                    {"path": "lib/lexer.py", "type": "blob"},
                    {"path": "tests/test_parser.py", "type": "blob"},
                ],
            },
        )
    )
    router.get(f"{API}/labels").mock(
        return_value=httpx.Response(200, json=[{"name": "good first issue"}])
    )
    router.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "number": 3,
                        "title": "Older parser bug",
                        "html_url": "https://github.com/acme/lib/issues/3",
                        "closed_at": _iso(1000),
                        "labels": [{"name": "good first issue"}],
                    }
                ]
            },
        )
    )
    router.get(url__regex=rf"{API}/issues/3/timeline.*").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "event": "cross-referenced",
                    "source": {
                        "issue": {
                            "number": 30,
                            "title": "Fix parser bug",
                            "html_url": "https://github.com/acme/lib/pull/30",
                            "repository": {"full_name": "acme/lib"},
                            "pull_request": {"merged_at": _iso(1001)},
                            "created_at": _iso(1000 + 86400 * 2),
                            "user": {"login": "newbie"},
                        }
                    },
                }
            ],
        )
    )
    router.get(f"{API}/pulls/30/files").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"filename": "lib/parser.py", "additions": 5, "deletions": 1},
                {"filename": "tests/test_parser.py", "additions": 9, "deletions": 0},
            ],
        )
    )
    router.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(200, json={"items": [{"path": "lib/lexer.py"}]})
    )


@respx.mock
def test_issue_pointers_resolves_files_and_learns_from_past_fixes() -> None:
    _mock(respx)
    data = GSoCToolkit().issue_pointers("acme/lib#12")
    files = data["files_likely_involved"]
    assert files[0]["path"] == "lib/parser.py" and files[0]["confidence"] == "stack trace"
    assert 40 in files[0]["lines"]
    assert data["search_links"][0]["identifier"] == "tokenize_line"
    assert "token" in data["code_search_note"].lower()
    fix = data["similar_fixes"][0]
    assert fix["pull_request"]["number"] == 30 and fix["pull_request"]["confidence"] == "closing PR"
    assert fix["files"] == ["lib/parser.py", "tests/test_parser.py"]
    assert fix["days_to_merge"] == 2
    assert data["fix_norm"]["touches_tests_pct"] == 100
    assert data["similar_label"] == "good first issue"


@respx.mock
def test_issue_pointers_uses_code_search_with_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    from git_into_gsoc import config

    config.get_settings.cache_clear()
    _mock(respx)
    data = GSoCToolkit().issue_pointers("https://github.com/acme/lib/issues/12")
    assert data["code_search"][0] == {"identifier": "tokenize_line", "paths": ["lib/lexer.py"]}
    assert any(
        f["confidence"] == "code search" and f["path"] == "lib/lexer.py"
        for f in data["files_likely_involved"]
    )


@respx.mock
def test_cli_pointers_renders_tables() -> None:
    _mock(respx)
    result = runner.invoke(app, ["pointers", "acme/lib#12"])
    assert result.exit_code == 0, result.output
    assert "lib/parser.py" in result.stdout
    assert "Fix norm here" in result.stdout
    assert "#30" in result.stdout


def test_an_issue_that_names_no_file_gets_a_title_word_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = GSoCToolkit()
    gh = toolkit.github
    monkeypatch.setattr(gh, "token", "t")
    monkeypatch.setattr(
        gh,
        "get_issue",
        lambda *a: {"number": 972, "title": "Two undo/redo methods do not join up", "body": ""},
    )
    monkeypatch.setattr(gh, "get_repo", lambda *a: {"default_branch": "main"})
    monkeypatch.setattr(gh, "git_tree", lambda *a: {"sha": "abc", "tree": []})
    monkeypatch.setattr(gh, "list_labels", lambda *a: [])
    queries: list[str] = []

    def search_code(query: str, per_page: int = 8) -> list[dict[str, str]]:
        queries.append(query)
        return [{"path": "td.vue/src/service/x6/graph/keys.js"}]

    monkeypatch.setattr(gh, "search_code", search_code)
    data = toolkit.issue_pointers("OWASP/threat-dragon#972")
    assert queries == ["undo redo repo:OWASP/threat-dragon"]
    first = data["files_likely_involved"][0]
    assert first["path"].endswith("keys.js") and first["confidence"] == "title words"


def test_title_word_search_falls_back_to_the_longest_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = GSoCToolkit()
    gh = toolkit.github
    monkeypatch.setattr(gh, "token", "t")
    issue = {"number": 4274, "title": "upload file - exceeded 250mb", "body": ""}
    monkeypatch.setattr(gh, "get_issue", lambda *a: issue)
    monkeypatch.setattr(gh, "get_repo", lambda *a: {"default_branch": "main"})
    monkeypatch.setattr(gh, "git_tree", lambda *a: {"sha": "abc", "tree": []})
    monkeypatch.setattr(gh, "list_labels", lambda *a: [])
    queries: list[str] = []

    def search_code(query: str, per_page: int = 8) -> list[dict[str, str]]:
        queries.append(query)
        return [] if len(queries) == 1 else [{"path": "server/utils/fileUtils.js"}]

    monkeypatch.setattr(gh, "search_code", search_code)
    data = toolkit.issue_pointers("processing/p5.js-web-editor#4274")
    assert queries == [
        "exceeded upload repo:processing/p5.js-web-editor",
        "exceeded repo:processing/p5.js-web-editor",
    ]
    assert data["files_likely_involved"][0]["path"] == "server/utils/fileUtils.js"
