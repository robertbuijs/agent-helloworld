"""GitHub MCP toolset — HTTP, read-only, narrow toolsets."""

from __future__ import annotations

import logging
import os
from typing import Optional

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
DEFAULT_TOOLSETS = "repos,issues,pull_requests"


def build_github_toolset() -> Optional[McpToolset]:
    """Build a read-only GitHub MCP toolset, or None if no token is configured.

    Uses X-MCP-Readonly and a narrow X-MCP-Toolsets list so Phase 1 stays
    retrieval-focused even if the model tries a write-shaped tool name.
    """
    token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        or ""
    ).strip()
    if not token:
        logger.warning(
            "GITHUB_TOKEN / GITHUB_PERSONAL_ACCESS_TOKEN not set; "
            "GitHub MCP tools will be unavailable."
        )
        return None

    url = os.getenv("GITHUB_MCP_URL", DEFAULT_GITHUB_MCP_URL).strip()
    toolsets = os.getenv("GITHUB_MCP_TOOLSETS", DEFAULT_TOOLSETS).strip()

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-MCP-Readonly": "true",
                "X-MCP-Toolsets": toolsets,
            },
        ),
        tool_name_prefix="github_",
    )
