# Enterprise Assistant (Phase 1)

Python [ADK](https://adk.dev/) conversational agent for **Gemini Enterprise**:

- Read-only **Jira / Atlassian** via MCP (`tool_filter` allow-list)
- Read-only **GitHub** via remote MCP (`X-MCP-Readonly` + narrow toolsets)
- Deployed with `AdkApp` → Agent Runtime (`reasoningEngine`)
- Registered on a Gemini Enterprise app for chat in the Gemini Enterprise UI

Writes, custom MCP, and multi-agent orchestration are **Phase 2+**.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add tokens — never commit .env
adk web agents/enterprise_assistant
```

Default model: `gemini-flash-latest` (override with `AGENT_MODEL`).

## Layout

```text
agents/enterprise_assistant/   # ADK package (root_agent)
  agent.py
  instructions.py
  tools/github.py
  tools/atlassian.py
scripts/deploy_agent_runtime.py
docs/RUNBOOK.md                # secrets, deploy, register, smoke checklist
docs/atlassian-runtime-auth.md # Runtime auth spike findings
.env.example
requirements.txt
pyproject.toml
```

## Deploy + register

See **[docs/RUNBOOK.md](docs/RUNBOOK.md)**. Short version:

```bash
# After GCP ADC + staging bucket + Secret Manager secrets:
python scripts/deploy_agent_runtime.py
# → projects/.../locations/.../reasoningEngines/...
# Then: Gemini Enterprise → Add agent → Custom agent via Agent Runtime
```

## Safety (Phase 1)

- Agent instructions refuse create/update/delete.
- GitHub: `X-MCP-Readonly: true`, toolsets `repos,issues,pull_requests`.
- Atlassian: HTTP MCP + `tool_filter` excluding write tools.
