# Install & wire-up

## One-shot installer

From the repo root:

```bash
./install.sh
```

Installs the Python package (CLI + MCP), copies the Agent Skill into common assistant skill directories, and prints MCP config snippets.

Options:

```bash
./install.sh --skill-only      # only install the skill files
./install.sh --mcp-only       # package + MCP hints, skip skill copy
./install.sh --user-skills    # force user-level skill install
```

## Manual Python install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
git-into-gsoc doctor
```

Set a GitHub token for better rate limits:

```bash
export GITHUB_TOKEN=ghp_...   # or GH_TOKEN
```

## Skill locations (portable Agent Skills)

The installer copies `skills/git-into-gsoc/` to:

| Assistant | Path |
|-----------|------|
| Cursor | `~/.cursor/skills/git-into-gsoc/` and `~/.agents/skills/git-into-gsoc/` |
| Claude Code | `~/.claude/skills/git-into-gsoc/` |
| Codex | `~/.codex/skills/git-into-gsoc/` |
| Gemini CLI | `~/.gemini/skills/git-into-gsoc/` (if present) |

Project-local alternative: copy into `.agents/skills/git-into-gsoc/` or `.cursor/skills/git-into-gsoc/`.

## MCP server config

Stdio command after install:

```bash
git-into-gsoc mcp
# equivalent: python -m git_into_gsoc.mcp_server
```

### Cursor (`~/.cursor/mcp.json` or project `.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "git-into-gsoc": {
      "command": "git-into-gsoc",
      "args": ["mcp"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

### Claude Code / Claude Desktop

Add an MCP server entry with command `git-into-gsoc` and args `["mcp"]`.

### Codex

Register the same stdio server in your Codex MCP settings.

## Verify

```bash
git-into-gsoc program --year 2027
git-into-gsoc orgs --tech python -n 5
git-into-gsoc progress summary
```

In your coding assistant, ask: “Using git-into-gsoc, help me shortlist GSoC orgs for Python scientific computing.”
