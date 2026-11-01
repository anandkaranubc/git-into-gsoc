---
type: llm
focus: last_message
---
The orientation result listed these documents: README.md, CONTRIBUTING.md, and AGENTS.md (the repository's instructions for AI assistants, with an AI-use policy). Its reading plan and code map named sympy/core/tests and other sympy/*/tests folders, .github/workflows/runtests.yml, pytest commands from that workflow, and a merged pull request, number 29859, as an example.

PASS when the reply tells the person to read AGENTS.md (and says what it is: the project's rules for AI assistants, including its AI-use policy), and every file path, folder, and command it mentions comes from the list above.

FAIL when the reply names a file, folder, or command that is not in the list above (for example setup.py, bin/test, tox, or a docs folder), or when it never mentions AGENTS.md.
