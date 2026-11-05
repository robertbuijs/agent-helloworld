"""Root ADK agent for Phase 1 — conversational, read-only Jira + GitHub."""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from google.adk.agents import Agent

from .instructions import PHASE1_INSTRUCTION
from .tools import build_atlassian_toolset, build_github_toolset
from .tools.runtime_toolset import RuntimeEnvToolset

load_dotenv()

DEFAULT_MODEL = "gemini-flash-latest"


def _build_tools() -> List[object]:
    # Do not call the builders here. Import (and the pickle taken by
    # agent_engines.create) runs before Agent Runtime injects Secret Manager
    # env vars. RuntimeEnvToolset builds the MCP clients on first use.
    return [
        RuntimeEnvToolset(build_github_toolset),
        RuntimeEnvToolset(build_atlassian_toolset),
    ]


root_agent = Agent(
    name="enterprise_assistant",
    model=os.getenv("AGENT_MODEL", DEFAULT_MODEL),
    description=(
        "Conversational assistant that retrieves read-only Jira and GitHub "
        "information for Gemini Enterprise users. Phase 1 cannot create, "
        "update, or delete anything."
    ),
    instruction=PHASE1_INSTRUCTION,
    tools=_build_tools(),
)
