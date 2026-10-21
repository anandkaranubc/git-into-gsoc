from __future__ import annotations

import json
from pathlib import Path

from git_into_gsoc.gsoc.client import GSoCClient
from git_into_gsoc.http_client import CachedHttpClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeHttp(CachedHttpClient):
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def get_json(self, url: str, **kwargs: object) -> object:  # type: ignore[override]
        return self.payload


def test_search_organizations_ranks_python_science() -> None:
    raw = json.loads((FIXTURES / "organizations_sample.json").read_text(encoding="utf-8"))
    client = GSoCClient(http=FakeHttp(raw))  # type: ignore[arg-type]
    results = client.search_organizations(technologies=["python"], topics=["science"], limit=5)
    assert results
    assert results[0].name == "SymPy"
    assert results[0].match_score > 0


def test_get_organization_fuzzy() -> None:
    raw = json.loads((FIXTURES / "organizations_sample.json").read_text(encoding="utf-8"))
    client = GSoCClient(http=FakeHttp(raw))  # type: ignore[arg-type]
    org = client.get_organization("wikimedia")
    assert org is not None
    assert "Wikimedia" in org.name


def test_github_hints_from_blog_url() -> None:
    raw = json.loads((FIXTURES / "organizations_sample.json").read_text(encoding="utf-8"))
    client = GSoCClient(http=FakeHttp(raw))  # type: ignore[arg-type]
    org = client.get_organization("SymPy")
    assert org is not None
    assert "sympy" in [h.lower() for h in org.github_hints]
