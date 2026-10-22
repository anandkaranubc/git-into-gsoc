# Privacy

git-into-gsoc runs on your own computer. It has no online service of its own and no account system, it collects no analytics, and the project never receives anything about you unless you choose to send it. This page applies to every way of running it: the command line, the MCP server that your AI assistant starts, the plugins and extensions, and the Agent Skill.

## What it reads from the internet

Only public data, from these places:

| Service | What the tool asks for |
|---|---|
| summerofcode.withgoogle.com | The program timeline and the list of accepted organizations |
| api.gsocorganizations.dev | Past years' organizations and project titles |
| api.github.com | Public repositories, issues, pull requests, and labels you ask about, and the public profile of a GitHub username you give it |
| commits.ecosyste.ms | Public commit counts for a repository |
| Each organization's own ideas page | The page the organization published for GSoC |
| raw.githubusercontent.com | Ideas and wiki pages that an organization keeps in a GitHub repository |
| A GitLab server, such as gitlab.com, gitlab.gnome.org, or invent.kde.org | Only when you check a GitLab issue link: that issue, its labels, assignees, and merge requests |

Each service sees a normal web request from your computer: your IP address and what was asked for, such as an organization or repository name. The tool never posts, comments, opens pull requests, or changes anything on any of them.

## Your GitHub token

A token is optional. If you have one (in `GITHUB_TOKEN`, `GH_TOKEN`, `GIG_GITHUB_TOKEN`, or from `gh auth token`), the tool sends it only to GitHub's API, to raise the request limit. It is never written to a file, printed, or sent anywhere else. Public data needs no token scopes.

A GitLab token (`GITLAB_TOKEN` or `GIG_GITLAB_TOKEN`) is optional too. If you set one, it is sent only to the GitLab server it belongs to (`GITLAB_HOST`, `gitlab.com` by default), to read issue comments that GitLab hides without a sign-in.

## What it saves on your computer

- **A cache** of the public responses above, so repeated questions are fast and stay within GitHub's limits. Old entries are deleted automatically.
- **Your progress file**, only when you or your assistant save something: your profile (for example the technologies you know, your interests, hours per week, and your GitHub username if you add it), the organizations and issues you track, and notes you write.

`git-into-gsoc doctor` prints where both folders are. Delete them at any time. Nothing in them is uploaded.

## Feedback you choose to send

`git-into-gsoc feedback` opens a GitHub issue form in your browser with three facts filled in: the tool version, the Python version, and your operating system's name. Nothing else is added, and nothing is sent until you read the form and press Submit on GitHub, where it becomes a public issue under your account.

## Your AI assistant

When you use git-into-gsoc through an assistant, the assistant sends what you type and the tool's results to its own provider (for example Anthropic, OpenAI, GitHub, or Google), under that provider's privacy terms. git-into-gsoc does not see or store those conversations.

## Contact

Questions or concerns: open an issue at https://github.com/anandkaranubc/git-into-gsoc/issues. For a security problem, follow [SECURITY.md](../SECURITY.md).
