# Architecture

## Goals

1. Portable guidance (Agent Skills) that works offline as playbooks
2. Live intelligence (MCP/CLI) for GitHub + GSoC archive data
3. Shared domain logic so CLI and MCP never drift
4. Safe defaults for beginners (availability checks, ethics, official citations)

## Component diagram

```
┌─────────────────────┐     ┌──────────────────────┐
│  Coding assistants  │────▶│  Agent Skill (md)    │
│ Cursor/Claude/Codex │     │  journey playbooks   │
└─────────┬───────────┘     └──────────────────────┘
          │ MCP / shell
          ▼
┌─────────────────────┐
│  git-into-gsoc CLI  │
│  / FastMCP server   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  GSoCToolkit        │  service.py facade
└─────┬───────────┬───┘
      │           │
      ▼           ▼
 GitHubClient   GSoCClient      ProgressStore
 (REST+cache)   (archive API)   (local JSON)
      │           │
      ▼           ▼
  scoring/*    timeline + guidance
```

## Design choices

| Choice | Rationale |
|--------|-----------|
| Python 3.11+ | MCP official SDK, typing, packaging maturity |
| MCP Python SDK (`MCPServer`) | Minimal boilerplate, wide client support |
| Typer + Rich | Pleasant CLI DX for humans debugging agents |
| Disk HTTP cache | Reduce rate-limit pain during iterative agent loops |
| Soft scores not ML | Transparent, tunable, testable heuristics |
| Skill progressive disclosure | Keep `SKILL.md` small; load references on demand |
| Archive API for orgs | No unofficial scraping of Google; clear provenance |

## Extensibility

* New MCP tools → implement on `GSoCToolkit`, wrap in `mcp_server.py`, add CLI if useful
* New scoring signals → `scoring/` + `data/scoring_weights.json` documentation
* New journey phase → `JourneyPhase` enum + `guidance.PHASE_GUIDES` + skill table

## Non-goals

* Guaranteeing GSoC acceptance
* Auto-submitting proposals
* Writing opaque AI PRs on the user's behalf
* Replacing org-specific mentor instructions
