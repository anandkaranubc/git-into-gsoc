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
