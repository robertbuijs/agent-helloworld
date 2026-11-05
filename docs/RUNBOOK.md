# Phase 1 runbook — Enterprise Assistant

Conversational ADK agent with **read-only** Jira + GitHub, deployed to Agent Runtime and registered on Gemini Enterprise.

## Prerequisites

| Item | Notes |
| --- | --- |
| GCP project | Hosts Agent Runtime (`reasoningEngine`) |
| Region | Match Gemini Enterprise app location rules (`global` app → any Runtime region; `us`/`eu` apps → matching Runtime region) |
| Staging bucket | Empty GCS bucket, e.g. `gs://my-agent-staging` |
| Gemini Enterprise app | Existing app where you will register the agent |
| GitHub PAT | Read access to target orgs/repos |
| Atlassian auth | API token (Basic) or service-account API key (Bearer); org admin must enable API-token auth on Rovo MCP |

## Secrets (never commit)

1. Copy `.env.example` → `.env` for local use.
2. For Runtime, create Secret Manager secrets (recommended):

```bash
# GitHub PAT (raw token string)
printf '%s' "$GITHUB_TOKEN" | gcloud secrets create github-token \
  --data-file=- --project="$GOOGLE_CLOUD_PROJECT"

# Atlassian Authorization header value, e.g. "Basic …" or "Bearer …"
printf '%s' "$ATLASSIAN_MCP_AUTH_HEADER" | gcloud secrets create atlassian-mcp-auth \
  --data-file=- --project="$GOOGLE_CLOUD_PROJECT"
```

3. Grant the Agent Runtime / Reasoning Engine service agent
   `roles/secretmanager.secretAccessor` on those secrets.

Set in `.env` / CI:

```text
SM_GITHUB_TOKEN_SECRET=github-token
SM_GITHUB_TOKEN_VERSION=latest
SM_ATLASSIAN_AUTH_SECRET=atlassian-mcp-auth
SM_ATLASSIAN_AUTH_VERSION=latest
```

### Atlassian Runtime auth (Phase 1 finding)

- Official ADK sample (`npx mcp-remote` + browser OAuth) is **local-only**.
- For Agent Runtime use **HTTP** `https://mcp.atlassian.com/v2/mcp` with:
  - Personal token: `Authorization: Basic base64(email:api_token)`
  - Service account: `Authorization: Bearer <api_key>`
- Admin must enable API-token authentication (Atlassian Administration → Rovo → Rovo MCP server → Authentication).
- Phase 1 scopes (minimum): `read:jira:agent-interface`, `search:jira:agent-interface` (add Confluence read/search if needed).
- API tokens are not bound to a `cloudId`; the agent should call `getAccessibleAtlassianResources` or accept a user-provided cloudId.
- Write tools are excluded via ADK `tool_filter` even if the MCP server exposes them.

## Local smoke test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill tokens
adk web agents/enterprise_assistant
# or: adk run agents/enterprise_assistant
```

Suggested prompts:

1. “Open Jira ticket KEY-123 and summarize status / assignee.”
2. “Search Jira with JQL: project = KEY AND status = 'In Progress'.”
3. “Summarize open PRs in org/repo.”
4. “Create a Jira ticket titled Test” → agent must **refuse** (Phase 1).

## Deploy to Agent Runtime

```bash
export GOOGLE_CLOUD_PROJECT=…
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_CLOUD_STORAGE_BUCKET=gs://…   # or STAGING_BUCKET=
# ADC: gcloud auth application-default login
# or: GOOGLE_APPLICATION_CREDENTIALS=…

python scripts/deploy_agent_runtime.py --dry-run   # validate
python scripts/deploy_agent_runtime.py             # create reasoningEngine
```

On success the script prints and writes:

```text
projects/PROJECT/locations/LOCATION/reasoningEngines/RESOURCE_ID
```

to `remote_agent_resource.txt` (gitignored).

### One-command deploy (once secrets exist)

```bash
python scripts/deploy_agent_runtime.py
```

## Register on Gemini Enterprise

Console path ([docs](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)):

1. Google Cloud console → **Gemini Enterprise** → open your app.
2. **Agents** → **Add agent**.
3. **Custom agent via Agent Runtime**.
4. Skip or configure OAuth authorizations only if the agent must call Google APIs as the end user (not required for shared GitHub/Jira service tokens).
5. Set:
   - **Agent name** — e.g. `Enterprise Assistant`
   - **Describe your agent** — used for routing; include that it retrieves Jira issues and GitHub repos/PRs (read-only).
   - **Agent Runtime resource path** — the `projects/…/reasoningEngines/…` value from deploy.
6. **Create**.

Optional: also catalog in Agent Registry for discovery; **chat in the Gemini Enterprise UI requires app registration**, not Registry alone.

Cross-project: if Runtime and Gemini Enterprise apps differ, grant the documented cross-project ADK access permissions before registering.

## Smoke checklist (E2E)

After registration:

- [ ] Gemini Enterprise UI lists **Enterprise Assistant**.
- [ ] Selecting the agent and asking a known Jira key returns live fields.
- [ ] Asking about a known GitHub repo/PR returns live data.
- [ ] Asking to create/update/delete a ticket or PR is refused.
- [ ] Missing credentials produce a clear error, not invented data.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Deploy fails on staging | Bucket exists? `gs://` prefix? Vertex AI API enabled? |
| Secret not injected | Secret ID/version correct? Runtime SA has `secretAccessor`? |
| GitHub tools empty | PAT scopes; `X-MCP-Readonly` / toolsets; token secret populated |
| Atlassian 401 | API-token auth enabled by admin? Header `Basic`/`Bearer` correct? |
| Atlassian cloudId errors | Call `getAccessibleAtlassianResources` or pass cloudId explicitly |
| Agent not in chat UI | Registered on the **Gemini Enterprise app**, not only Agent Registry |
| Region mismatch | Align Runtime region with Gemini Enterprise app location |

## Phase 1 out of scope

Custom MCP, Jira/GitHub writes, multi-agent orchestration, Model Armor hardening — see plan Phase 2+.
