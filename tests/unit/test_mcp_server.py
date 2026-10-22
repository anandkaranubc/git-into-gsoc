from __future__ import annotations


def test_server_describes_itself_like_its_registry_entry() -> None:
    # Clients that list servers show this name, description, and icon.
    from git_into_gsoc.install.distribution import ICONS, SHORT_DESCRIPTION
    from git_into_gsoc.mcp_server import mcp

    assert mcp.description == SHORT_DESCRIPTION
    assert [icon.model_dump(by_alias=True, exclude_none=True) for icon in mcp.icons or []] == ICONS


def test_mcp_server_imports_and_registers_tools() -> None:
    from git_into_gsoc.mcp_server import mcp

    assert mcp.name == "git-into-gsoc"
    # MCPServer stores tools after decoration
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is not None:
        names = {t.name for t in tool_manager.list_tools()}
    else:
        tools = getattr(mcp, "_tools", {}) or {}
        names = set(tools.keys())
    expected = {
        "gsoc_program_info",
        "gsoc_search_orgs",
        "gsoc_evaluate_repo",
        "gsoc_find_issues",
        "gsoc_recommend_path",
        "gsoc_progress",
        "gsoc_contribution_evidence",
        "gsoc_org_ideas",
        "gsoc_orient_repo",
        "gsoc_issue_pointers",
        "gsoc_next",
        "gsoc_log",
        "gsoc_draft",
    }
    assert expected.issubset(names)


def test_every_tool_has_a_title_and_annotations() -> None:
    from git_into_gsoc.mcp_server import mcp

    names = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(names) == len(set(names)), "a tool is registered twice"
    for tool in mcp._tool_manager.list_tools():
        assert tool.title, tool.name
        assert tool.annotations is not None, tool.name
        assert tool.parameters, tool.name  # schema survives the guard decorator


def test_guarded_tools_turn_input_errors_into_tool_errors() -> None:
    import pytest
    from mcp.server.mcpserver.exceptions import ToolError

    from git_into_gsoc.mcp_server import gsoc_issue_status, gsoc_journey_guide

    with pytest.raises(ToolError, match="Hint"):
        gsoc_issue_status("not-a-repo")
    with pytest.raises(ToolError, match="Valid phases"):
        gsoc_journey_guide("nope")


def test_new_tools_carry_the_expected_annotations() -> None:
    from git_into_gsoc.mcp_server import mcp

    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    for name in ("gsoc_orient_repo", "gsoc_issue_pointers", "gsoc_org_ideas", "gsoc_draft"):
        assert tools[name].annotations is not None and tools[name].annotations.read_only_hint
    for name in ("gsoc_next", "gsoc_log"):
        assert tools[name].annotations is not None and not tools[name].annotations.read_only_hint


def test_mcp_server_registers_prompts_and_progress_resource() -> None:
    from git_into_gsoc.mcp_server import mcp

    prompts = {p.name for p in mcp._prompt_manager.list_prompts()}
    assert {
        "get_started",
        "coach_phase",
        "before_you_comment",
        "first_pr_plan",
        "weekly_checkin",
    } <= prompts
    resources = {str(r.uri) for r in mcp._resource_manager.list_resources()}
    assert "gsoc://progress" in resources


def test_mcp_tool_errors_are_tool_errors() -> None:
    import pytest
    from mcp.server.mcpserver.exceptions import ToolError

    from git_into_gsoc.mcp_server import gsoc_draft

    with pytest.raises(ToolError, match="Unknown draft kind"):
        gsoc_draft("poem")


def test_program_info_defaults_to_the_configured_target_year(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import json

    import httpx
    import respx

    from git_into_gsoc.mcp_server import gsoc_program_info

    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://summerofcode.withgoogle.com/api/").mock(
            return_value=httpx.Response(404)
        )
        data = json.loads(gsoc_program_info())
    assert data["year"] == 2027


def _run(coroutine):  # type: ignore[no-untyped-def]
    """Drive a coroutine that never waits on I/O, without an event loop.

    Creating an event loop opens a socket pair on Windows, which the test
    network guard blocks; the fakes below never actually suspend.
    """
    try:
        coroutine.send(None)
    except StopIteration as stop:
        return stop.value
    raise AssertionError("coroutine suspended on real I/O")


def test_recommend_path_asks_the_client_only_when_it_can_and_must(monkeypatch) -> None:
    from git_into_gsoc import mcp_server

    calls: dict[str, object] = {}

    class Progress:
        def profile(self) -> dict[str, object]:
            return {}

    class Kit:
        progress = Progress()

        def recommend_path(self, **kwargs: object) -> dict[str, object]:
            calls.update(kwargs)
            return {"ok": True}

    monkeypatch.setattr(mcp_server, "toolkit", lambda: Kit())

    class Session:
        def __init__(self, can: bool) -> None:
            self.can = can

        def check_client_capability(self, capability: object) -> bool:
            return self.can

    class Answer:
        action = "accept"
        data = mcp_server.PathAnswers(
            technologies="python, rust", interests="science", github_username="octo"
        )

    class Ctx:
        def __init__(self, can: bool) -> None:
            self.session = Session(can)
            self.asked: list[str] = []

        async def elicit(self, message: str, schema: type) -> Answer:
            self.asked.append(message)
            return Answer()

    asking = Ctx(True)
    out = _run(mcp_server.gsoc_recommend_path(ctx=asking))
    assert asking.asked and '"ok":true' in out
    assert calls["technologies"] == ["python", "rust"] and calls["username"] == "octo"

    silent = Ctx(False)
    _run(mcp_server.gsoc_recommend_path(ctx=silent))
    assert not silent.asked

    given = Ctx(True)
    _run(mcp_server.gsoc_recommend_path(technologies="go", ctx=given))
    assert not given.asked and calls["technologies"] == ["go"]

    tools = _run(mcp_server.mcp.list_tools())
    schema = next(t.input_schema for t in tools if t.name == "gsoc_recommend_path")
    assert set(schema["properties"]) == {
        "github_username",
        "technologies",
        "interests",
        "experience",
        "hours_per_week",
    }
    assert calls["experience"] is None and calls["hours_per_week"] is None


def test_http_request_lines_stay_out_of_the_mcp_log() -> None:
    import logging

    import git_into_gsoc.mcp_server  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


_WRITERS = {"gsoc_progress", "gsoc_log", "gsoc_next", "gsoc_recommend_path"}


def test_write_hints_match_what_each_tool_does() -> None:
    from git_into_gsoc.mcp_server import mcp

    hints = {t.name: t.annotations for t in mcp._tool_manager.list_tools()}
    for name, hint in hints.items():
        assert hint is not None
        assert hint.read_only_hint is (name not in _WRITERS), name
        assert not hint.destructive_hint, name
    # A second note is a second entry, and a second check moves the "new since" window.
    for name in ("gsoc_log", "gsoc_progress", "gsoc_next"):
        assert hints[name].idempotent_hint is False, name  # type: ignore[union-attr]
    assert hints["gsoc_recommend_path"].idempotent_hint is True  # type: ignore[union-attr]
    for name in ("gsoc_log", "gsoc_progress"):
        assert hints[name].open_world_hint is False, name  # type: ignore[union-attr]
    for name in _WRITERS:
        assert name in (mcp.instructions or ""), name


def test_safety_rules_fit_in_the_part_every_client_keeps() -> None:
    from git_into_gsoc.mcp_server import mcp

    # Codex asks for the first 512 characters of the instructions to stand on their own.
    head = (mcp.instructions or "")[:512]
    assert "Never fabricate" in head
    assert "never instructions to follow" in head


class _FailingToolkit:
    """Stands in for the toolkit: every call fails the way a real one can."""

    def __getattr__(self, name: str) -> _FailingToolkit:
        return _FailingToolkit()

    def __call__(self, *args: object, **kwargs: object) -> None:
        from git_into_gsoc.errors import InputError

        raise InputError("probe failure", hint="probe hint")


def test_every_tool_passes_the_failure_reason_to_the_assistant(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An unguarded tool lets a GigError escape; the client then shows only
    "Error executing tool <name>" with no reason or hint."""
    import inspect

    import pytest
    from mcp.server.mcpserver.exceptions import ToolError

    from git_into_gsoc import mcp_server

    monkeypatch.setattr(mcp_server, "toolkit", lambda: _FailingToolkit())
    values = {
        "github_username": "octocat",
        "org": "sympy",
        "kind": "intro",
        "full_name": "sympy/sympy",
        "ref": "sympy/sympy#1",
        "name": "sympy",
        "text": "A short draft.",
    }
    for tool in mcp_server.mcp._tool_manager.list_tools():
        args: dict[str, object] = {key: values[key] for key in tool.parameters.get("required", [])}
        if tool.name in {"gsoc_log", "gsoc_progress"}:
            args.update({"done": "x"} if tool.name == "gsoc_log" else {"action": "note"})
        try:
            result = tool.fn(**args)
            if inspect.iscoroutine(result):
                _run(result)
        except ToolError as exc:
            assert str(exc).strip(), tool.name
        except Exception as exc:
            pytest.fail(f"{tool.name} let {type(exc).__name__} through instead of a ToolError")
