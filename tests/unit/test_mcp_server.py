from __future__ import annotations


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
    }
    assert expected.issubset(names)


def test_every_tool_has_a_title_and_annotations() -> None:
    from git_into_gsoc.mcp_server import mcp

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
