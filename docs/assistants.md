# Use git-into-gsoc in your AI assistant

git-into-gsoc gives an assistant two things:

- An **Agent Skill**: written instructions that teach the assistant to coach you through GSoC without inventing organizations, issues, or deadlines.
- An **MCP server**: a small program on your computer that lets the assistant run the tool's searches and checks. MCP stands for Model Context Protocol.

Neither the plugins nor setup pre-approve anything: your assistant still asks before running a tool, as its own settings say. Each tool declares whether it only reads or also saves to your local progress file, and assistants use that to decide when to ask.

Pick your assistant below. Each route installs both parts, and each one says how to update and remove it. If you also want the `git-into-gsoc` command in your terminal, use the [one-line installer](guide/02-install.md) and then `git-into-gsoc setup`. Setup configures every assistant it finds at once.

## Before you start: install uv

Every plugin and link below starts the server with [uv](https://docs.astral.sh/uv/), a free tool that installs Python programs together with the Python they need. If `uv --version` prints a version, you already have it. Otherwise install it once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS, Linux, WSL
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

Open a new terminal afterwards. The first time an assistant starts the server, uv downloads what it needs, which can take up to a minute. Later starts take about a second.

## Claude Code

```bash
claude plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc
```

Inside a Claude Code session you can type the same thing as `/plugin install git-into-gsoc --marketplace anandkaranubc/git-into-gsoc`. Versions older than 2.1.292 need two steps: `claude plugin marketplace add anandkaranubc/git-into-gsoc`, then `claude plugin install git-into-gsoc@git-into-gsoc`. Start a new session afterwards.

- **Update:** `claude plugin update git-into-gsoc@git-into-gsoc`. To update automatically, open `/plugin`, go to Marketplaces, and turn on auto-update for `git-into-gsoc`.
- **Remove:** `claude plugin uninstall git-into-gsoc@git-into-gsoc`, then `claude plugin marketplace remove git-into-gsoc`.
- **Permission questions:** Claude Code asks before it first uses each tool. Pick the answer that stops asking for that tool, and each question comes up only once. The tools read public data, and four of them save to your progress file on your computer and nowhere else.
- **For a team:** commit this as `.claude/settings.json` in your project, and Claude Code offers the plugin to everyone who opens it:

  ```json
  {
    "extraKnownMarketplaces": {
      "git-into-gsoc": { "source": { "source": "github", "repo": "anandkaranubc/git-into-gsoc" } }
    },
    "enabledPlugins": { "git-into-gsoc@git-into-gsoc": true }
  }
  ```

The same plugin works in Claude Desktop's Code tab. In claude.ai and Claude Desktop chats, you can add the marketplace under Customize, Plugins, Add marketplace. The skill then works in chat, but chat does not run local MCP servers, so it cannot fetch live data there.

## Codex (CLI and the ChatGPT desktop app)

```bash
codex plugin marketplace add anandkaranubc/git-into-gsoc
codex plugin add git-into-gsoc@git-into-gsoc
```

- **Update:** `codex plugin marketplace upgrade git-into-gsoc`, then run `codex plugin add git-into-gsoc@git-into-gsoc` again.
- **Remove:** `codex plugin remove git-into-gsoc@git-into-gsoc`, then `codex plugin marketplace remove git-into-gsoc`.
- The Codex extension for VS Code and other editors does not support plugins. Use `git-into-gsoc setup` there; it shares Codex's settings file.
- With `git-into-gsoc setup --scope project`, Codex reads the project's `.codex/config.toml` only after you mark that folder as trusted, which Codex asks about the first time you open it there. Until then `codex mcp list` shows no server. User scope (the default) has no such step.
- To install only the skill, type this in Codex: `$skill-installer install https://github.com/anandkaranubc/git-into-gsoc/tree/main/skills/git-into-gsoc`

## GitHub Copilot CLI

```bash
copilot plugin marketplace add anandkaranubc/git-into-gsoc
copilot plugin install git-into-gsoc@git-into-gsoc
```

- **Update:** `copilot plugin update git-into-gsoc@git-into-gsoc`.
- **Remove:** `copilot plugin uninstall git-into-gsoc@git-into-gsoc`.

VS Code picks up plugins installed this way too.

## VS Code (GitHub Copilot)

Choose one:

- **The plugin** (skill and server): open the Command Palette, run **Chat: Install Plugin From Source**, and enter `https://github.com/anandkaranubc/git-into-gsoc`.
- **Only the server, with one click:** use the VS Code button below. VS Code shows the server and asks you to confirm.
- **`git-into-gsoc setup`**: writes `~/.copilot/mcp-config.json`, which VS Code's Copilot sessions and Copilot CLI both read, and puts the skill in `~/.agents/skills`.

Installed plugins are listed in the Extensions view under `@agentPlugins`, where you can manage or remove them. To remove a server added with the button, run **MCP: Open User Configuration** and delete the `git-into-gsoc` entry.

## Visual Studio (GitHub Copilot, Windows)

Visual Studio 2026, or Visual Studio 2022 version 17.14 or newer, adds the server with the Visual Studio button below. It asks you to confirm, then runs the newest release with uv. The button adds the server only, not the skill.

- **Update:** the server checks PyPI and runs the newest release each time it starts.
- **Remove:** delete the `git-into-gsoc` entry from the `.mcp.json` file that lists it. For servers in every solution, that is `%USERPROFILE%\.mcp.json`.

## Cursor

Run `git-into-gsoc setup` after the [one-line installer](guide/02-install.md). This is the route we test, and it gives Cursor both the skill and the server. Or use the Cursor button below for the server alone. Cursor asks you to confirm, then adds it to `~/.cursor/mcp.json`. To add the skill too, run `npx skills add anandkaranubc/git-into-gsoc -g -a cursor`.

- **Update:** a server added with the button checks PyPI and runs the newest release each time it starts. For setup, re-run the installer.
- **Remove:** delete the `git-into-gsoc` entry from `~/.cursor/mcp.json`, or run `git-into-gsoc setup --remove --assistant cursor`.

## Gemini CLI

```bash
gemini extensions install https://github.com/anandkaranubc/git-into-gsoc --auto-update
```

- Gemini CLI starts MCP servers only in folders you trust. Answer yes when it asks, or run `/permissions` in the folder.
- **Update:** with `--auto-update` it updates itself at start. Otherwise run `gemini extensions update git-into-gsoc`.
- **Remove:** `gemini extensions uninstall git-into-gsoc`.
- Since 18 June 2026, Gemini CLI needs a paid Gemini API key or Gemini Code Assist Standard or Enterprise. On a free Google account, use Antigravity.

## Antigravity

```bash
agy plugin install https://github.com/anandkaranubc/git-into-gsoc
```

Antigravity converts the extension into a plugin with the skill and the server.

- **Update:** run the same command again.
- **Remove:** `agy plugin uninstall git-into-gsoc`.
- `git-into-gsoc setup --assistant antigravity` works too.

## Windsurf (Devin Desktop)

Run `git-into-gsoc setup` after the [one-line installer](guide/02-install.md). It writes Devin Desktop's `~/.config/devin/mcp_config.json`, or `~/.codeium/windsurf/mcp_config.json` for Windsurf before it was renamed. It puts the skill in `~/.agents/skills`, which Devin Desktop reads.

## Claude Desktop (without the plugin)

Every [release](https://github.com/anandkaranubc/git-into-gsoc/releases/latest) has a `git-into-gsoc.mcpb` file, an MCP bundle. [Download the newest one](https://github.com/anandkaranubc/git-into-gsoc/releases/latest/download/git-into-gsoc.mcpb) and open it, or drag it into Claude Desktop's Settings, Extensions. Claude Desktop shows what it installs and asks you to confirm. It also offers an optional GitHub token field; leave it empty unless you hit GitHub's limit of 60 requests an hour.

- **Update:** a bundle does not update itself. Download the newest file again and open it.
- **Remove:** Settings, Extensions, then uninstall `git-into-gsoc`.

## Any other assistant

Most assistants read skills from `~/.agents/skills` and accept MCP servers in a settings file. This includes Zed, Goose, OpenCode, Amp, JetBrains Junie, Cline, Kilo Code, Kiro, Warp, Qwen Code, Factory Droid, and Augment. Two community tools set both up for you:

```bash
npx skills add anandkaranubc/git-into-gsoc -g
npx add-mcp "uvx git-into-gsoc@latest mcp" --name git-into-gsoc
```

The first copies the skill; the second asks which assistants to add the server to. Both need [Node.js](https://nodejs.org/). Kiro also has a button below.

## One-click buttons

These add only the MCP server. Each opens a web page that hands the server to the app, and the app asks you to confirm. Most run the newest release from [PyPI](https://pypi.org/project/git-into-gsoc/) with `uvx git-into-gsoc@latest mcp`, so they need only uv. uv checks for a newer release each time the assistant starts the server, so it stays current. The Claude Desktop button downloads the newest release's bundle instead; see [Claude Desktop](#claude-desktop-without-the-plugin). For a server that also starts offline, use a plugin or `git-into-gsoc setup` instead.

<!-- generated:install-links -->
[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=git-into-gsoc&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJnaXQtaW50by1nc29jQGxhdGVzdCIsIm1jcCJdfQ%3D%3D) [![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_server-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=git-into-gsoc&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22git-into-gsoc%40latest%22%2C%22mcp%22%5D%7D) [![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install_server-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=git-into-gsoc&config=%7B%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22git-into-gsoc%40latest%22%2C%22mcp%22%5D%7D&quality=insiders) [![Add to Kiro](https://kiro.dev/images/add-to-kiro.svg)](https://kiro.dev/launch/mcp/add?name=git-into-gsoc&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22git-into-gsoc%40latest%22%2C%22mcp%22%5D%7D) [![Install in Visual Studio](https://img.shields.io/badge/Visual_Studio-Install_server-5C2D91?style=flat-square&logo=visualstudio&logoColor=white)](https://vs-open.link/mcp-install?%7B%22name%22%3A%22git-into-gsoc%22%2C%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22git-into-gsoc%40latest%22%2C%22mcp%22%5D%7D) [![Download for Claude Desktop](https://img.shields.io/badge/Claude_Desktop-Download_extension-D97757?style=flat-square&logo=claude&logoColor=white)](https://github.com/anandkaranubc/git-into-gsoc/releases/latest/download/git-into-gsoc.mcpb)
<!-- /generated:install-links -->

## Plugin or setup?

| | Plugin or extension | `git-into-gsoc setup` |
|---|---|---|
| Needs | uv | The [one-line installer](guide/02-install.md) |
| You also get | Nothing else | The `git-into-gsoc` command in your terminal |
| Updates | With the assistant's own update command | Run the installer again |
| Server starts | From the plugin's own copy, so it always matches the skill | From the installed command, offline and fastest |
| Assistants | One at a time | Every one it finds, in one run |

Use one route per assistant. Setup skips an assistant that already has the plugin, so you never get the server twice.

## What we test

`scripts/check_agents.py` installs git-into-gsoc into each assistant command it finds, the way that assistant's users would. It uses a throwaway home folder, signs in nowhere, and calls no model. Then it checks that the assistant can start the server. Before installing from a checkout, it runs each format's own validator where one exists. Buttons cannot be clicked in a script, so for those it writes exactly what the app writes after you confirm, and lets the app start the server. CI runs it on Linux on every change to the files these assistants read, and weekly with each assistant's newest release, installing from GitHub.

| Assistant | What is checked |
|---|---|
| Claude Code | Plugin and setup: the server connects |
| Codex | Plugin and setup: the server answers, from the plugin's own folder |
| Gemini CLI | Extension and setup: the server connects |
| Copilot CLI | Plugin and setup: the server is registered. Copilot starts servers only for a signed-in session, so CI cannot start it; a signed-in check on 2026-10-21 (no prompt sent) showed Copilot launching the plugin's server from the plugin folder, and that command answering with 25 tools |
| Antigravity | Plugin and setup: the converted plugin's server answers |
| Cursor | The button's config and setup: Cursor's agent CLI starts the server and lists its tools |
| VS Code | The button's config: VS Code accepts it and the server answers |
| Visual Studio | Not in CI, because Visual Studio runs only on Windows. A test decodes the button's link, and its redirect to Visual Studio was checked on 2026-10-22 |
| Claude Desktop | The bundle passes the MCP bundle validator, then is unpacked and started the way Desktop runs it |

Not checked automatically: the click itself in each app, VS Code's Install Plugin From Source, and Devin Desktop. Each follows its vendor's documented format. Please [report a problem](https://github.com/anandkaranubc/git-into-gsoc/issues) if one does not work for you.

[Privacy](privacy.md) · [Assistant setup guide](guide/03-connect-your-ai-assistant.md) · [Troubleshooting](troubleshooting.md) · [MCP tool reference](mcp.md) · [Guide contents](README.md)
