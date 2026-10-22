"""Exception hierarchy with user-facing hints."""

from __future__ import annotations

from datetime import UTC, datetime


class GigError(Exception):
    """Base error for expected, user-explainable failures."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint

    def to_dict(self) -> dict[str, str]:
        data = {"error": str(self), "type": type(self).__name__}
        if self.hint:
            data["hint"] = self.hint
        return data


class InputError(GigError, ValueError):
    """Invalid user input (repo names, usernames, phases, ...)."""


class AmbiguousNameError(InputError):
    """A name fits more than one organization equally well."""

    def __init__(self, name: str, candidates: list[str]) -> None:
        shown = candidates[:8]
        more = f" and {len(candidates) - len(shown)} more" if len(candidates) > len(shown) else ""
        super().__init__(
            f"'{name}' fits more than one organization: {', '.join(shown)}{more}",
            hint=f'Repeat with the full name, for example "{shown[0]}".',
        )
        self.candidates = candidates


class HttpError(GigError):
    """A request that failed; `status_code` and `url` say where."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint)
        self.status_code = status_code
        self.url = url


class NotFoundError(HttpError):
    """A 404, or something this tool cannot read, such as a mirror's issues."""


class RateLimitError(HttpError):
    """GitHub's request limit was hit. The hint depends on the resource (core or
    search) and on whether a token was used."""

    def __init__(
        self,
        message: str,
        *,
        reset_at: datetime | None = None,
        status_code: int | None = 403,
        url: str | None = None,
        authenticated: bool = False,
        resource: str = "core",
    ) -> None:
        if resource == "search" and authenticated:
            hint = (
                "GitHub search allows 30 requests a minute, and other tools using the same "
                "token count too; wait a minute and run it again."
            )
        elif resource == "search":
            hint = (
                "GitHub search allows 10 requests a minute without a token and 30 with one; "
                "wait a minute, or run `gh auth login` to get the higher limit."
            )
        elif authenticated:
            hint = "Wait a few minutes; cached results keep working meanwhile."
        else:
            hint = (
                "Run `gh auth login` or set GITHUB_TOKEN to raise the limit from 60 to 5000 req/h."
            )
        super().__init__(message, status_code=status_code, url=url, hint=hint)
        self.reset_at = reset_at
        self.resource = resource

    @property
    def reset_in_seconds(self) -> int | None:
        if self.reset_at is None:
            return None
        return max(0, int((self.reset_at - datetime.now(UTC)).total_seconds()))


def reset_phrase(reset_at: datetime | None) -> str:
    """'resets in 22 minutes (03:56 UTC)': a countdown needs no time zone sum."""
    if reset_at is None:
        return ""
    minutes = max(1, -(-int((reset_at - datetime.now(UTC)).total_seconds()) // 60))
    return f"resets in {minutes} minute{'' if minutes == 1 else 's'} ({reset_at:%H:%M} UTC)"
