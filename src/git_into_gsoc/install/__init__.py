"""Install the Agent Skill and register the MCP server with local assistants.

Everything here is cross-platform Python so that ``git-into-gsoc setup`` is
the single install path on macOS, Linux, and Windows; ``install.sh`` and
``install.ps1`` only bootstrap the package and then call it.
"""

from git_into_gsoc.install.plan import plan_setup, run_removal, run_setup
from git_into_gsoc.install.skill import copy_skill, skill_source

__all__ = ["copy_skill", "plan_setup", "run_removal", "run_setup", "skill_source"]
