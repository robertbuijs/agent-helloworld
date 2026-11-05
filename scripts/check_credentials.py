#!/usr/bin/env python3
"""Report which Phase 1 deploy credentials are present (never prints secret values)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


def present(*names: str) -> bool:
    return any(bool((os.getenv(n) or "").strip()) for n in names)


def main() -> int:
    checks = {
        "GCP project": present("GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
        "GCP location": present("LOCATION", "GOOGLE_CLOUD_LOCATION"),
        "Staging bucket": present("STAGING_BUCKET", "GOOGLE_CLOUD_STORAGE_BUCKET"),
        "GCP ADC / credentials": present(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
        )
        or Path.home().joinpath(
            ".config/gcloud/application_default_credentials.json"
        ).is_file(),
        "GitHub token (env)": present("GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN"),
        "GitHub token (Secret Manager id)": present("SM_GITHUB_TOKEN_SECRET"),
        "Atlassian auth (env)": present(
            "ATLASSIAN_MCP_AUTH_HEADER",
            "ATLASSIAN_API_KEY",
        )
        or (
            present("ATLASSIAN_EMAIL")
            and present("ATLASSIAN_API_TOKEN", "JIRA_API_TOKEN")
        ),
        "Atlassian auth (Secret Manager id)": present("SM_ATLASSIAN_AUTH_SECRET"),
    }

    print("Phase 1 credential presence (values not shown):")
    for label, ok in checks.items():
        print(f"  [{'OK' if ok else '--'}] {label}")

    can_deploy = (
        checks["GCP project"]
        and checks["Staging bucket"]
        and checks["GCP ADC / credentials"]
    )
    print()
    if can_deploy:
        print("Minimum GCP deploy credentials look present. Run:")
        print("  python scripts/deploy_agent_runtime.py --dry-run")
        return 0

    print("Blocked: missing GCP project, staging bucket, and/or ADC credentials.")
    print("See docs/RUNBOOK.md and provide the items listed as [--].")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
