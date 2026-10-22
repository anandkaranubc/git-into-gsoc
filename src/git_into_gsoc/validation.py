"""Validation and parsing for GitHub identifiers.

Everything that ends up in an API path or a search query passes through here so
user (or model) input cannot traverse to other endpoints or inject qualifiers.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from git_into_gsoc.errors import InputError

_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_SEARCH_TERM_RE = re.compile(r"[^\w+#.\- ]", flags=re.UNICODE)
_GITHUB_HOSTS = {"github.com", "www.github.com"}


def validate_login(value: str, *, kind: str = "GitHub user/org") -> str:
    login = (value or "").strip().lstrip("@")
    if not _LOGIN_RE.match(login):
        raise InputError(
            f"Invalid {kind}: {value!r}",
            hint="Use the GitHub handle only, e.g. `octocat` or `sympy`.",
        )
    return login


_HOST_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)


def _split_github_path(value: str) -> list[str]:
    raw = value.strip()
    # SSH remote as printed by `git remote -v`: git@github.com:owner/repo.git
    ssh = re.match(r"^(?:ssh://)?git@github\.com[:/](.+)$", raw, re.IGNORECASE)
    if ssh:
        return [p for p in ssh.group(1).split("/") if p]
    # "gitlab.com/inkscape/inkscape" copied without its scheme: a GitHub owner never has
    # a dot in its name, so a first part that looks like a host name is another site.
    first = raw.split("/", 1)[0]
    elsewhere = "://" not in raw and bool(_HOST_RE.match(first))
    if raw.startswith(("http://", "https://")) or raw.startswith(tuple(_GITHUB_HOSTS)) or elsewhere:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        if parsed.netloc.lower() not in _GITHUB_HOSTS:
            raise InputError(
                f"Not a github.com URL: {value!r}",
                hint="This command reads GitHub only. For a project on GitLab or its own "
                "server, read its contributing guide there. `git-into-gsoc issue` does read "
                "an issue link from any GitLab server.",
            )
        return [p for p in parsed.path.split("/") if p]
    return [p for p in raw.split("/") if p]


def _is_github_link(value: str) -> bool:
    """A URL or SSH remote, as opposed to a bare owner/repo name."""
    raw = value.strip()
    return bool(
        re.match(r"^(?:ssh://)?git@github\.com[:/]", raw, re.IGNORECASE)
        or raw.startswith(("http://", "https://"))
        or raw.lower().startswith(tuple(_GITHUB_HOSTS))
    )


def parse_repo(value: str) -> tuple[str, str]:
    """Parse `owner/repo` or a GitHub URL into a validated (owner, repo) pair.

    A pasted link may go deeper (`.../tree/main/docs`); a bare name may not, since
    `a/b/c` is not a GitHub repository.
    """
    parts = _split_github_path(value or "")
    if len(parts) < 2 or (len(parts) > 2 and not _is_github_link(value or "")):
        raise InputError(
            f"Repository must look like owner/repo, got {value!r}",
            hint="Example: sympy/sympy or https://github.com/sympy/sympy",
        )
    owner = validate_login(parts[0], kind="repository owner")
    repo = parts[1].removesuffix(".git")
    if not _REPO_RE.match(repo) or repo in {".", ".."}:
        raise InputError(f"Invalid repository name: {parts[1]!r}")
    return owner, repo


def parse_issue_ref(value: str, number: int | None = None) -> tuple[str, str, int]:
    """Parse `owner/repo#123`, `owner/repo 123`, or an issue/PR URL."""
    raw = (value or "").strip()
    # URLs first: a pasted comment link (".../issues/12#issuecomment-34") or a URL with a
    # query string must resolve from its path, not from the text after "#".
    if number is None and ("://" in raw or raw.lower().startswith(tuple(_GITHUB_HOSTS))):
        try:
            parts = _split_github_path(raw)
        except InputError as exc:
            # "GitHub only" was wrong for `issue`, which reads GitLab links before it gets
            # here; some GSoC organizations also work on SourceForge or Savannah.
            raise InputError(
                f"Not a GitHub issue link: {value!r}",
                hint="`git-into-gsoc issue` also reads issue links from any GitLab server. "
                "For an issue on another site, open it there and read the whole thread for "
                "claims and linked patches before you comment.",
            ) from exc
        if len(parts) >= 4 and parts[2] in {"issues", "pull"}:
            owner, repo = parse_repo("/".join(parts[:2]))
            return owner, repo, _parse_number(parts[3])
    if number is None and "#" in raw:
        repo_part, _, num = raw.partition("#")
        owner, repo = parse_repo(repo_part)
        return owner, repo, _parse_number(num)
    parts = _split_github_path(raw)
    if number is None and len(parts) >= 4 and parts[2] in {"issues", "pull"}:
        owner, repo = parse_repo("/".join(parts[:2]))
        return owner, repo, _parse_number(parts[3])
    owner, repo = parse_repo(raw)
    if number is None:
        raise InputError(
            f"Missing issue number for {value!r}",
            hint="Use owner/repo#123, an issue URL, or pass the number separately.",
        )
    return owner, repo, _parse_number(str(number))


def _parse_number(value: str) -> int:
    try:
        num = int(value.strip())
    except ValueError as exc:
        raise InputError(f"Invalid issue number: {value!r}") from exc
    if num <= 0:
        raise InputError(f"Issue number must be positive, got {num}")
    return num


def search_term(value: str) -> str:
    """Make free text safe to embed in a GitHub search qualifier value."""
    cleaned = _SEARCH_TERM_RE.sub(" ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise InputError(f"Empty or invalid search term: {value!r}")
    return f'"{cleaned}"' if " " in cleaned else cleaned


def split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else value.split(",")
    return [item.strip() for item in items if item and item.strip()]


FIRST_GSOC_YEAR = 2005


def validate_year(year: int | None, *, latest: int) -> int | None:
    """A program year GSoC has had or is about to have; None or 0 means "not given"."""
    if not year:
        return None
    if not FIRST_GSOC_YEAR <= year <= latest:
        raise InputError(
            f"GSoC years run from {FIRST_GSOC_YEAR} to {latest}, got {year}",
            hint="Leave out the year to use the coming program.",
        )
    return year


_SKILL_QUALIFIER_RE = re.compile(
    r"^(?:a (?:little|bit of)|a little bit of|basic|basics of|some|beginner|intermediate|"
    r"advanced|learning|familiar with|good at|strong)\s+|\s*\((?:basic|beginner|learning|"
    r"some|intermediate|advanced)\)$",
    re.I,
)


def plain_skill(term: str) -> str:
    """ "a little python" -> "python": the level is useful to a person, not to a search."""
    cleaned = term.strip()
    while True:
        shorter = _SKILL_QUALIFIER_RE.sub("", cleaned).strip()
        if shorter == cleaned or not shorter:
            return cleaned
        cleaned = shorter
