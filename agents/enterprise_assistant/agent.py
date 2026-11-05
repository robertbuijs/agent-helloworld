"""Root ADK agent for Phase 1 — conversational, read-only Jira + GitHub."""

from __future__ import annotations

import logging
import os
from typing import List

from dotenv import load_dotenv
from google.adk.agents import Agent

from .instructions import PHASE1_INSTRUCTION
from .tools import build_atlassian_toolset, build_github_toolset

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"


def _build_tools() -> List[object]:
    tools: List[object] = []
    github = build_github_toolset()
    if github is not None:
        tools.append(github)
    atlassian = build_atlassian_toolset()
    if atlassian is not None:
        tools.append(atlassian)
    if not tools:
        logger.warning(
            "No MCP toolsets configured. Agent will be conversational only "
            "until GITHUB_TOKEN and/or Atlassian credentials are set."
        )
    return tools


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
