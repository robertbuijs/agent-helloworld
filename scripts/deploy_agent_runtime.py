#!/usr/bin/env python3
"""Deploy the Phase 1 ADK agent to Vertex AI Agent Runtime (reasoningEngine).

Reads configuration from environment / .env:

  GCP_PROJECT / GOOGLE_CLOUD_PROJECT
  LOCATION / GOOGLE_CLOUD_LOCATION
  STAGING_BUCKET / GOOGLE_CLOUD_STORAGE_BUCKET  (gs://…)
  Secret Manager IDs for GitHub + Atlassian (optional)

Usage (from repo root, with ADC or service account credentials)::

  python scripts/deploy_agent_runtime.py
  python scripts/deploy_agent_runtime.py --dry-run

On success, prints the reasoningEngine resource path and writes it to
``remote_agent_resource.txt`` (gitignored).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _require(name: str, value: Optional[str]) -> str:
    if not value:
        raise SystemExit(
            f"Missing required config: {name}. Set it in the environment or .env "
            f"(see .env.example)."
        )
    return value


def _normalize_bucket(bucket: str) -> str:
    bucket = bucket.strip()
    if not bucket.startswith("gs://"):
        bucket = f"gs://{bucket}"
    return bucket.rstrip("/")


def build_env_vars() -> Dict[str, Any]:
    """Build Agent Runtime env_vars, preferring Secret Manager references."""
    env_vars: Dict[str, Any] = {
        "AGENT_MODEL": _env("AGENT_MODEL", default="gemini-flash-latest"),
        "GITHUB_MCP_URL": _env(
            "GITHUB_MCP_URL", default="https://api.githubcopilot.com/mcp/"
        ),
        "GITHUB_MCP_TOOLSETS": _env(
            "GITHUB_MCP_TOOLSETS", default="repos,issues,pull_requests"
        ),
        "ATLASSIAN_MCP_TRANSPORT": "http",
        "ATLASSIAN_MCP_URL": _env(
            "ATLASSIAN_MCP_URL", default="https://mcp.atlassian.com/v2/mcp"
        ),
    }

    gh_secret = _env("SM_GITHUB_TOKEN_SECRET")
    if gh_secret:
        env_vars["GITHUB_TOKEN"] = {
            "secret": gh_secret,
            "version": _env("SM_GITHUB_TOKEN_VERSION", default="latest"),
        }
    else:
        token = _env("GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN")
        if token:
            print(
                "WARNING: injecting GITHUB_TOKEN as a plain env var. "
                "Prefer SM_GITHUB_TOKEN_SECRET (Secret Manager) for Runtime.",
                file=sys.stderr,
            )
            env_vars["GITHUB_TOKEN"] = token

    atl_secret = _env("SM_ATLASSIAN_AUTH_SECRET")
    if atl_secret:
        env_vars["ATLASSIAN_MCP_AUTH_HEADER"] = {
            "secret": atl_secret,
            "version": _env("SM_ATLASSIAN_AUTH_VERSION", default="latest"),
        }
    else:
        auth_header = _env("ATLASSIAN_MCP_AUTH_HEADER")
        if auth_header:
            print(
                "WARNING: injecting ATLASSIAN_MCP_AUTH_HEADER as a plain env var. "
                "Prefer SM_ATLASSIAN_AUTH_SECRET for Runtime.",
                file=sys.stderr,
            )
            env_vars["ATLASSIAN_MCP_AUTH_HEADER"] = auth_header
        else:
            api_key = _env("ATLASSIAN_API_KEY")
            if api_key:
                print(
                    "WARNING: injecting ATLASSIAN_API_KEY as a plain env var. "
                    "Prefer SM_ATLASSIAN_AUTH_SECRET for Runtime.",
                    file=sys.stderr,
                )
                env_vars["ATLASSIAN_API_KEY"] = api_key
            else:
                email = _env("ATLASSIAN_EMAIL")
                token = _env("ATLASSIAN_API_TOKEN", "JIRA_API_TOKEN")
                if email and token:
                    print(
                        "WARNING: injecting ATLASSIAN_EMAIL + ATLASSIAN_API_TOKEN "
                        "as plain env vars. Prefer SM_ATLASSIAN_AUTH_SECRET.",
                        file=sys.stderr,
                    )
                    env_vars["ATLASSIAN_EMAIL"] = email
                    env_vars["ATLASSIAN_API_TOKEN"] = token

    return env_vars


def preflight(project: str, location: str, staging_bucket: str) -> None:
    print("Deploy preflight")
    print(f"  project:         {project}")
    print(f"  location:        {location}")
    print(f"  staging_bucket:  {staging_bucket}")
    print(f"  display_name:    {_env('AGENT_DISPLAY_NAME', default='Enterprise Assistant')}")
    env_vars = build_env_vars()
    secret_keys = [k for k, v in env_vars.items() if isinstance(v, dict)]
    plain_secretish = [
        k
        for k, v in env_vars.items()
        if isinstance(v, str)
        and k
        in {
            "GITHUB_TOKEN",
            "ATLASSIAN_MCP_AUTH_HEADER",
            "ATLASSIAN_API_KEY",
            "ATLASSIAN_API_TOKEN",
        }
    ]
    print(f"  secret_refs:     {secret_keys or '(none)'}")
    print(f"  plain_secrets:   {plain_secretish or '(none)'}")
    if "GITHUB_TOKEN" not in env_vars:
        print(
            "  WARNING: no GitHub credential configured — Runtime agent will "
            "lack GitHub tools.",
            file=sys.stderr,
        )
    if not any(
        k in env_vars
        for k in (
            "ATLASSIAN_MCP_AUTH_HEADER",
            "ATLASSIAN_API_KEY",
            "ATLASSIAN_API_TOKEN",
        )
    ):
        print(
            "  WARNING: no Atlassian credential configured — Runtime agent will "
            "lack Jira tools.",
            file=sys.stderr,
        )


def deploy(*, dry_run: bool = False) -> Optional[str]:
    project = _require(
        "GCP_PROJECT / GOOGLE_CLOUD_PROJECT",
        _env("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
    )
    location = _require(
        "LOCATION / GOOGLE_CLOUD_LOCATION",
        _env("LOCATION", "GOOGLE_CLOUD_LOCATION", default="us-central1"),
    )
    staging_bucket = _normalize_bucket(
        _require(
            "STAGING_BUCKET / GOOGLE_CLOUD_STORAGE_BUCKET",
            _env("STAGING_BUCKET", "GOOGLE_CLOUD_STORAGE_BUCKET"),
        )
    )
    display_name = _env("AGENT_DISPLAY_NAME", default="Enterprise Assistant")
    description = _env(
        "AGENT_DESCRIPTION",
        default=(
            "Read-only Jira and GitHub assistant for Gemini Enterprise (Phase 1)."
        ),
    )
    gcs_dir_name = _env("GCS_DIR_NAME", default="enterprise-assistant")
    env_vars = build_env_vars()

    preflight(project, location, staging_bucket)

    if dry_run:
        print("Dry run only — not calling agent_engines.create.")
        return None

    import vertexai
    from vertexai import agent_engines

    try:
        from vertexai.preview.reasoning_engines import AdkApp
    except ImportError:  # pragma: no cover - SDK layout varies by version
        from vertexai.agent_engines import AdkApp  # type: ignore

    from agents.enterprise_assistant.agent import root_agent

    vertexai.init(
        project=project,
        location=location,
        staging_bucket=staging_bucket,
    )

    app = AdkApp(agent=root_agent, enable_tracing=True)

    requirements = [
        "google-cloud-aiplatform[agent_engines,adk]>=1.100.0",
        "google-adk>=1.5.0",
        "mcp>=1.9.0",
        "python-dotenv>=1.0.0",
    ]

    print("Creating Agent Runtime (reasoningEngine)… this can take several minutes.")
    remote_app = agent_engines.create(
        app,
        display_name=display_name,
        description=description,
        requirements=requirements,
        extra_packages=["./agents"],
        gcs_dir_name=gcs_dir_name,
        env_vars=env_vars,
    )

    resource_name = remote_app.resource_name
    out = REPO_ROOT / "remote_agent_resource.txt"
    out.write_text(resource_name + "\n", encoding="utf-8")
    print("Deployed successfully.")
    print(f"  resource_name: {resource_name}")
    print(f"  wrote:         {out}")
    print()
    print("Next: register this path in Gemini Enterprise → Add agent →")
    print("Custom agent via Agent Runtime. See docs/RUNBOOK.md.")
    return resource_name


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print preflight without deploying.",
    )
    args = parser.parse_args(argv)
    try:
        deploy(dry_run=args.dry_run)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — surface deploy errors clearly
        print(f"Deploy failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
