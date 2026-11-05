"""MCP toolset that reads credentials when the agent runs, not when it is pickled."""

from __future__ import annotations

import hashlib
import os
from typing import Callable, Optional, Sequence

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset

# Values that change which MCP client is built. Hashed so a resolved toolset
# can be reused without keeping another copy of the secret on this object.
_ENV_KEYS: tuple[str, ...] = (
    "GITHUB_TOKEN",
    "GITHUB_PERSONAL_ACCESS_TOKEN",
    "GITHUB_MCP_URL",
    "GITHUB_MCP_TOOLSETS",
    "ATLASSIAN_MCP_TRANSPORT",
    "ATLASSIAN_MCP_URL",
    "ATLASSIAN_MCP_AUTH_HEADER",
    "ATLASSIAN_API_KEY",
    "ATLASSIAN_EMAIL",
    "ATLASSIAN_API_TOKEN",
    "JIRA_API_TOKEN",
    "ATLASSIAN_MCP_TIMEOUT",
)


def _env_fingerprint(keys: Sequence[str]) -> str:
    material = "\n".join((os.getenv(key) or "").strip() for key in keys)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class RuntimeEnvToolset(BaseToolset):
    """Build an MCP toolset from the process environment on first use.

    ``agent_engines.create`` pickles ``root_agent`` before Agent Runtime
    applies Secret Manager ``env_vars``. Constructing ``McpToolset`` at import
    either drops Jira/GitHub tools (tokens are unset on the deploy machine)
    or freezes deploy-time tokens and ``ATLASSIAN_MCP_TRANSPORT`` into the
    pickle. This wrapper is safe to pickle: the real client is created later,
    when those Runtime variables exist.
    """

    def __init__(
        self,
        factory: Callable[[], Optional[BaseToolset]],
        env_keys: Sequence[str] = _ENV_KEYS,
    ) -> None:
        super().__init__()
        self._factory = factory
        self._env_keys = tuple(env_keys)
        self._inner: Optional[BaseToolset] = None
        self._fingerprint: Optional[str] = None

    def __reduce_ex__(self, _protocol: int):
        return (self.__class__, (self._factory, self._env_keys))

    def __repr__(self) -> str:
        name = getattr(self._factory, "__name__", repr(self._factory))
        return f"{self.__class__.__name__}(factory={name})"

    async def _resolve(self) -> Optional[BaseToolset]:
        fingerprint = _env_fingerprint(self._env_keys)
        if self._fingerprint == fingerprint:
            return self._inner
        if self._inner is not None:
            await self._inner.close()
            self._inner = None
        self._inner = self._factory()
        self._fingerprint = fingerprint
        return self._inner

    async def get_tools(
        self,
        readonly_context: Optional[ReadonlyContext] = None,
    ) -> list[BaseTool]:
        inner = await self._resolve()
        if inner is None:
            return []
        prefixed = getattr(inner, "get_tools_with_prefix", None)
        if prefixed is not None:
            return await prefixed(readonly_context)
        return await inner.get_tools(readonly_context)

    async def close(self) -> None:
        if self._inner is not None:
            await self._inner.close()
            self._inner = None
            self._fingerprint = None
