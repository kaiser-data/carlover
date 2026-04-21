#!/usr/bin/env python3
"""
Deploy Carlover to Daytona.

Creates a persistent sandbox, uploads the project, installs dependencies,
and starts the uvicorn server. Prints the public preview URL on success.

Usage:
    python scripts/deploy_daytona.py
    python scripts/deploy_daytona.py --stop      # stop running sandbox
    python scripts/deploy_daytona.py --status    # show sandbox status
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_env() -> dict[str, str]:
    """Load required env vars from .env file."""
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def get_client(env: dict[str, str]):
    try:
        from daytona_sdk import Daytona, DaytonaConfig
    except ImportError:
        print("ERROR: daytona-sdk not installed. Run: pip install daytona-sdk")
        sys.exit(1)

    api_key = env.get("DAYTONA_API_KEY", "")
    if not api_key or api_key == "your_daytona_api_key_here":
        print("ERROR: DAYTONA_API_KEY not set in .env")
        sys.exit(1)

    return Daytona(DaytonaConfig(
        api_key=api_key,
        api_url=env.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
    ))


def deploy(env: dict[str, str]) -> None:
    daytona = get_client(env)

    print("Creating Carlover sandbox on Daytona...")
    from daytona_sdk import CreateSandboxFromImageParams
    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image="python:3.12-slim",
            language="python",
            public=True,             # no OAuth required — accessible without login
            auto_stop_interval=0,    # 0 = never auto-stop (persistent service)
            auto_delete_interval=0,  # 0 = never auto-delete
            env_vars={
                "FEATHERLESS_API_KEY": env.get("FEATHERLESS_API_KEY", ""),
                "FEATHERLESS_BASE_URL": env.get("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
                "FEATHERLESS_MODEL_ORCHESTRATOR": env.get("FEATHERLESS_MODEL_ORCHESTRATOR", "Qwen/Qwen2.5-14B-Instruct"),
                "FEATHERLESS_MODEL_REASONING": env.get("FEATHERLESS_MODEL_REASONING", "Qwen/Qwen2.5-72B-Instruct"),
                "FEATHERLESS_MODEL_VISION": env.get("FEATHERLESS_MODEL_VISION", "mistralai/Mistral-Small-3.2-24B-Instruct-2506"),
                "FEATHERLESS_MODEL_RESPONSE": env.get("FEATHERLESS_MODEL_RESPONSE", "Qwen/Qwen2.5-72B-Instruct"),
                "HUGGINGFACE_API_KEY": env.get("HUGGINGFACE_API_KEY", ""),
                "SUPABASE_URL": env.get("SUPABASE_URL", ""),
                "SUPABASE_KEY": env.get("SUPABASE_KEY", ""),
                "DAYTONA_API_KEY": env.get("DAYTONA_API_KEY", ""),
                "DAYTONA_API_URL": env.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
                "ADAC_PROVIDER": env.get("ADAC_PROVIDER", "real"),
                "SCRAPER_API_KEY": env.get("SCRAPER_API_KEY", ""),
                "DEBUG": env.get("DEBUG", "false"),
                "LOG_LEVEL": env.get("LOG_LEVEL", "INFO"),
            },
        )
    )

    print(f"Sandbox ID: {sandbox.id}")
    print("Installing dependencies...")

    # Install from PyPI (project is uploaded inline)
    cmds = [
        "pip install fastapi uvicorn[standard] pydantic pydantic-settings "
        "langgraph langchain-core langchain-openai supabase openai "
        "python-multipart loguru python-dotenv httpx daytona-sdk Pillow --quiet",
    ]
    for cmd in cmds:
        r = sandbox.process.exec(cmd, timeout=120)
        if getattr(r, "exit_code", 0) != 0:
            print(f"WARNING: command failed: {cmd}\n{r.result}")

    # Upload project files
    print("Uploading project files...")
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        # Skip venv, cache, test files for production
        parts = rel.parts
        if any(p in parts for p in (".venv", "__pycache__", ".git", "tests", "scripts")):
            continue
        remote_path = f"/carlover/{rel}"
        try:
            sandbox.fs.upload_file(str(path), remote_path)
        except Exception as exc:
            print(f"  skip {rel}: {exc}")

    # Upload skills markdown files
    for path in (ROOT / "app" / "skills").glob("*.md"):
        rel = path.relative_to(ROOT)
        sandbox.fs.upload_file(str(path), f"/carlover/{rel}")

    # Upload frontend static files
    for path in (ROOT / "frontend").rglob("*"):
        if path.is_file():
            rel = path.relative_to(ROOT)
            sandbox.fs.upload_file(str(path), f"/carlover/{rel}")

    # Start the server as a background process
    print("Starting uvicorn server on port 8000...")
    from daytona_sdk._sync.process import SessionExecuteRequest
    sandbox.process.create_session("server")
    sandbox.process.execute_session_command(
        "server",
        SessionExecuteRequest(
            command="cd /carlover && uvicorn app.main:app --host 0.0.0.0 --port 8000",
            run_async=True,
        ),
    )

    # Wait for server to be ready
    time.sleep(5)

    # Get preview URL
    try:
        preview = sandbox.get_preview_link(port=8000)
        signed = sandbox.create_signed_preview_url(port=8000)
        preview_url = getattr(signed, 'url', str(signed))
        token = getattr(preview, 'token', getattr(preview, 'url', str(preview)))
        print("\n" + "=" * 60)
        print("Carlover is running on Daytona!")
        print(f"Sandbox ID : {sandbox.id}")
        print(f"Preview URL: {preview_url}")
        print(f"Token URL  : {token}")
        print("=" * 60)
        print("\nTest with:")
        print(f'curl -s "{preview_url}/health"')
    except Exception as exc:
        print(f"\nServer started. Could not fetch preview URL: {exc}")
        print(f"Sandbox ID: {sandbox.id}")

    # Save sandbox ID locally for --stop / --status
    (ROOT / ".daytona_sandbox_id").write_text(sandbox.id)


def stop(env: dict[str, str]) -> None:
    sandbox_file = ROOT / ".daytona_sandbox_id"
    if not sandbox_file.exists():
        print("No .daytona_sandbox_id file found. Nothing to stop.")
        return
    sandbox_id = sandbox_file.read_text().strip()
    daytona = get_client(env)
    print(f"Stopping sandbox {sandbox_id}...")
    daytona.stop(sandbox_id)
    print("Stopped.")


def status(env: dict[str, str]) -> None:
    sandbox_file = ROOT / ".daytona_sandbox_id"
    if not sandbox_file.exists():
        print("No .daytona_sandbox_id file found.")
        return
    sandbox_id = sandbox_file.read_text().strip()
    daytona = get_client(env)
    sandbox = daytona.get(sandbox_id)
    print(f"Sandbox ID : {sandbox_id}")
    print(f"State      : {getattr(sandbox, 'state', 'unknown')}")
    try:
        preview = sandbox.get_preview_link(port=8000)
        print(f"Preview    : {preview}")
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Carlover to Daytona")
    parser.add_argument("--stop", action="store_true", help="Stop the running sandbox")
    parser.add_argument("--status", action="store_true", help="Show sandbox status")
    args = parser.parse_args()

    env = load_env()

    if args.stop:
        stop(env)
    elif args.status:
        status(env)
    else:
        deploy(env)
