"""Atlassian / Jira MCP toolset — read-only via tool_filter.

Runtime auth spike (Phase 1 finding)
------------------------------------
The official ADK Atlassian sample uses ``npx mcp-remote`` + browser OAuth.
That works locally but is unsuitable for Agent Runtime (no interactive browser).

Atlassian now supports non-interactive auth on the HTTP MCP endpoint
``https://mcp.atlassian.com/v2/mcp``:

* Personal API token: ``Authorization: Basic base64(email:api_token)``
* Service account API key: ``Authorization: Bearer <api_key>``

Org admin must enable API-token auth under Atlassian Administration → Rovo →
Rovo MCP server → Authentication. Prefer HTTP + API token/API key for Runtime;
keep stdio ``mcp-remote`` only for interactive local smoke tests.

See: https://developer.atlassian.com/cloud/rovo-mcp/guides/configuring-authentication-via-api-token/
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)

DEFAULT_ATLASSIAN_MCP_URL = "https://mcp.atlassian.com/v2/mcp"

# Phase 1 allow-list: retrieval / metadata only. Explicitly excludes
# create/edit/transition/comment/update tools exposed by the Atlassian MCP.
ATLASSIAN_READ_TOOL_FILTER = [
    "atlassianUserInfo",
    "getAccessibleAtlassianResources",
    "getJiraIssue",
    "searchJiraIssuesUsingJql",
    "lookupJiraAccountId",
    "getJiraIssueRemoteIssueLinks",
    "getVisibleJiraProjects",
    "getJiraProjectIssueTypesMetadata",
    "getJiraIssueTypeMetaWithFields",
    "getTransitionsForJiraIssue",  # read transitions metadata only; do not call transitionJiraIssue
    "getConfluenceSpaces",
    "getConfluencePage",
    "getPagesInConfluenceSpace",
    "getConfluencePageFooterComments",
    "getConfluencePageInlineComments",
    "getConfluencePageDescendants",
    "searchConfluenceUsingCql",
    "search",
    "fetch",
]


def _authorization_header() -> Optional[str]:
    """Resolve a ready-to-send Authorization header value for Atlassian MCP."""
    ready = (os.getenv("ATLASSIAN_MCP_AUTH_HEADER") or "").strip()
    if ready:
        return ready

    bearer = (os.getenv("ATLASSIAN_API_KEY") or "").strip()
    if bearer:
        return f"Bearer {bearer}"

    email = (os.getenv("ATLASSIAN_EMAIL") or "").strip()
    token = (
        os.getenv("ATLASSIAN_API_TOKEN")
        or os.getenv("JIRA_API_TOKEN")
        or ""
    ).strip()
    if email and token:
        encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    return None


def build_atlassian_http_toolset() -> Optional[McpToolset]:
    """Preferred Runtime path: Streamable HTTP + API token / API key."""
    auth = _authorization_header()
    if not auth:
        logger.warning(
            "No Atlassian MCP credentials found "
            "(ATLASSIAN_MCP_AUTH_HEADER, ATLASSIAN_API_KEY, or "
            "ATLASSIAN_EMAIL+ATLASSIAN_API_TOKEN). HTTP toolset disabled."
        )
        return None

    url = os.getenv("ATLASSIAN_MCP_URL", DEFAULT_ATLASSIAN_MCP_URL).strip()
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            headers={"Authorization": auth},
        ),
        tool_filter=ATLASSIAN_READ_TOOL_FILTER,
        tool_name_prefix="jira_",
    )


def build_atlassian_stdio_toolset() -> McpToolset:
    """Local interactive fallback: npx mcp-remote (browser OAuth).

    Do not use this path on Agent Runtime — it requires an interactive browser.
    Enable with ATLASSIAN_MCP_TRANSPORT=stdio for local smoke tests only.
    """
    timeout = float(os.getenv("ATLASSIAN_MCP_TIMEOUT", "60"))
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "mcp-remote", "https://mcp.atlassian.com/v1/mcp"],
            ),
            timeout=timeout,
        ),
        tool_filter=ATLASSIAN_READ_TOOL_FILTER,
        tool_name_prefix="jira_",
    )


def build_atlassian_toolset() -> Optional[McpToolset]:
    """Select Atlassian transport from env; default to HTTP for Runtime."""
    transport = (os.getenv("ATLASSIAN_MCP_TRANSPORT") or "http").strip().lower()
    if transport in {"stdio", "mcp-remote", "oauth"}:
        logger.info("Using Atlassian MCP via stdio/mcp-remote (local/OAuth).")
        return build_atlassian_stdio_toolset()
    return build_atlassian_http_toolset()
