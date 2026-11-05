# Atlassian MCP — Agent Runtime auth spike (Phase 1)

## Problem

The [official ADK Atlassian integration](https://adk.dev/integrations/atlassian/) uses:

```text
npx mcp-remote https://mcp.atlassian.com/v1/mcp
```

First run opens a **browser OAuth** consent flow. That is fine for `adk web` on a laptop. On **Agent Runtime** there is no interactive browser, so stdio `mcp-remote` OAuth cannot complete.

## Finding (recommended Runtime path)

Atlassian documents **API token authentication** for non-interactive / machine clients against the HTTP MCP endpoint:

- URL: `https://mcp.atlassian.com/v2/mcp` (v1 remains supported)
- Personal API token: `Authorization: Basic base64(email:api_token)`
- Service account API key: `Authorization: Bearer <api_key>`
- Guide: [Configuring authentication via API token](https://developer.atlassian.com/cloud/rovo-mcp/guides/configuring-authentication-via-api-token/)

### Org prerequisites

1. Admin enables API-token auth: **Atlassian Administration → Rovo → Rovo MCP server → Authentication**.
2. Token/API key includes Jira `agent-interface` scopes needed for Phase 1 reads, e.g. `read:jira:agent-interface`, `search:jira:agent-interface`.
3. Store the full `Authorization` header value (or email+token) in **Secret Manager**; inject via `env_vars` on `agent_engines.create`.

### Client implications

| Topic | Detail |
| --- | --- |
| cloudId | API tokens are **not** bound to a cloudId. Tools may require an explicit `cloudId`; call `getAccessibleAtlassianResources` first. |
| Tool coverage | Some tools (e.g. Code search, Teams) still require OAuth 2.1 and are unavailable with API tokens. |
| Domain allowlist | API-token auth bypasses OAuth redirect domain allowlists; IP allowlists still apply. |
| Local fallback | Set `ATLASSIAN_MCP_TRANSPORT=stdio` only for interactive laptop smoke tests. |

## Phase 1 implementation

`agents/enterprise_assistant/tools/atlassian.py`:

- Default transport: **HTTP** + Secret/env Authorization header.
- `tool_filter` allow-list of read/search/metadata tools only (no create/edit/transition/comment).
- Deploy script maps `SM_ATLASSIAN_AUTH_SECRET` → `ATLASSIAN_MCP_AUTH_HEADER` via Secret Manager `SecretRef`.

## Validation checklist

1. Admin confirms API-token auth is enabled.
2. `curl -I https://mcp.atlassian.com/v2/mcp -H "Authorization: …"` returns `200`.
3. Local agent with HTTP transport can `getJiraIssue` / JQL search.
4. Deployed Runtime agent can do the same without a browser.
5. Write tool names are absent from the model’s tool list (`tool_filter`).

## Residual risk

If the org **disallows** API-token MCP auth, Phase 1 Jira on Runtime is blocked until either:

- Admin enables it, or
- A different headless credential path (custom proxy / pre-authorized remote MCP) is provided.

Document that decision in the deploy status note before treating registration as complete.
