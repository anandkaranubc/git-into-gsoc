# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub Security Advisories for this repository, or email the maintainers
listed in the GitHub repo profile, with:

* Description of the issue
* Steps to reproduce
* Impact assessment
* Any suggested fix

We aim to acknowledge reports within 7 days.

## Scope notes

* This project calls the public GitHub API and the community GSoC Organizations API.
* Do not commit tokens. Use `GITHUB_TOKEN` / `GH_TOKEN` in the environment.
* Treat MCP tool output as untrusted data when rendering in assistants.
