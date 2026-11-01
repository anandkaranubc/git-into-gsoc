---
type: llm
focus: last_message
---
The orientation result for sympy/sympy listed README.md, CONTRIBUTING.md and AGENTS.md. AGENTS.md is the repository's instructions for AI assistants, and the result quoted its AI-use policy: contributors must understand and be able to explain every line they submit, and must say in the pull request that they used AI tools.

PASS when the reply tells the person to read AGENTS.md and says what it is: the project's own rules for AI assistants, including its policy on AI use.

FAIL when the reply never mentions AGENTS.md, or presents it as something other than the project's rules for AI assistants, or names a file the result did not contain, such as setup.py, tox.ini, a Makefile, or a docs/ folder (the result says doc/).
