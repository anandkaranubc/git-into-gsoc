"""A README section on contributing counts as the contributing guide."""

from __future__ import annotations

from typing import Any

import pytest

from git_into_gsoc.github.client import GitHubClient
from git_into_gsoc.github.repos import readme_contributing_section
from git_into_gsoc.models import RepoHealth
from git_into_gsoc.scoring.health import score_repo_health

RULES = (
    "Only issues labelled help wanted can be requested. Comment on the issue to ask, "
    "then wait to be assigned before you open a pull request. Pull requests for issues "
    "that were not assigned to you will be closed. Run the tests before you push."
)


def test_a_how_to_contribute_section_is_found_but_a_contributors_list_is_not() -> None:
    # Shaped like p5.js-website's README (2026-10-22): rules under "How To Contribute",
    # then a heading that only lists names.
    readme = f"# Site\n\nIntro.\n\n## How To Contribute\n\n{RULES}\n\n## Add Yourself to Contributors\n\nNames."
    section = readme_contributing_section(readme)
    assert section is not None and "wait to be assigned" in section
    assert "Names" not in section
    assert readme_contributing_section("# Site\n\n## Contributors\n\n" + RULES) is None


@pytest.mark.parametrize(
    "readme",
    [
        f"Project\n=======\n\nContributing\n------------\n\n{RULES}\n\nLicense\n-------\n\nMIT",
        f"<h1>Project</h1>\n<h2>Contribution guidelines</h2>\n{RULES}\n<h2>License</h2>\nMIT",
    ],
    ids=["setext-or-rest", "html"],
)
def test_other_heading_styles_are_read(readme: str) -> None:
    section = readme_contributing_section(readme)
    assert section is not None and "wait to be assigned" in section and "MIT" not in section


def test_comments_in_code_blocks_are_not_headings() -> None:
    # A shell comment in a fenced block once ended the section early (caught in review).
    readme = (
        "## Contributing\n\nSet up first:\n\n```bash\n# install the deps\nnpm ci\n```\n\n"
        f"{RULES}\n\n## License\n\nMIT"
    )
    section = readme_contributing_section(readme)
    assert section is not None and "wait to be assigned" in section and "MIT" not in section
    # And a comment that names contributing is not taken for the section's heading.
    fenced_only = f"# Tool\n\n```sh\n# how to contribute\n```\n\n{RULES}"
    assert readme_contributing_section(fenced_only) is None


def test_a_one_line_welcome_is_not_a_guide() -> None:
    assert (
        readme_contributing_section("# Tool\n\n## Contributing\n\nContributions welcome!\n") is None
    )


def test_the_readme_is_read_only_when_there_is_no_contributing_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GitHubClient()
    fetched: list[str] = []

    def raw(owner: str, repo: str, path: str) -> str:
        fetched.append(path)
        return f"## How to contribute\n\n{RULES}"

    monkeypatch.setattr(client, "_raw_file", raw)
    readme = {"html_url": "https://github.com/acme/site/blob/main/README.md"}
    profile: dict[str, Any] = {"files": {"readme": readme}}
    assert client._readme_guide_path("acme", "site", profile) == "README.md"
    with_file = {"files": {"readme": readme, "contributing": {"html_url": "x"}}}
    assert client._readme_guide_path("acme", "site", with_file) is None
    assert fetched == ["README.md"]


def test_a_readme_guide_earns_the_points_and_says_where_it_is() -> None:
    health = RepoHealth(
        full_name="acme/site",
        url="https://github.com/acme/site",
        has_contributing=True,
        contributing_source="readme",
    )
    scored = score_repo_health(health)
    guide = next(p for p in scored.points if p.signal == "CONTRIBUTING guide")
    assert (guide.earned, guide.most) == (12, 12)
    assert "Has contributing rules in its README (no separate CONTRIBUTING file)" in scored.signals
    assert not any("No CONTRIBUTING guide" in w for w in scored.warnings)


def test_the_merge_rate_is_a_plain_figure() -> None:
    # "Healthy merge rate (52% of human PRs)" read as praise in a blind beginner run.
    health = RepoHealth(
        full_name="acme/lib", url="https://github.com/acme/lib", prs_sampled=40, merge_rate=0.52
    )
    scored = score_repo_health(health)
    assert "52% of human PRs merged" in scored.signals
    assert not any("Healthy" in s for s in scored.signals)


def test_repo_ends_with_a_next_step_that_follows_the_grade() -> None:
    from git_into_gsoc.service import _repo_next_step

    good = _repo_next_step("acme/lib", "B")
    assert good.startswith("git-into-gsoc orient acme/lib") and "issues --repo acme/lib" in good
    weak = _repo_next_step("acme/lib", "C")
    assert weak.startswith("git-into-gsoc repos acme ")
