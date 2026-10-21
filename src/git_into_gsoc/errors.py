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
    pass


class RateLimitError(HttpError):
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
        if resource == "search":
            hint = (
                "GitHub search allows 10 requests a minute without a token and 30 with one; "
                "wait a minute, narrow the search with --repo or --org, or run `gh auth login`."
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
