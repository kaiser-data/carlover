"""
Sandbox Agent — executes diagnostic code in an ephemeral Daytona sandbox.

Useful for:
- Running OBD-II diagnostic parsers
- Executing automotive calculation scripts
- Safe execution of user-provided diagnostic snippets

Returns a structured SandboxAgentOutput. If Daytona is not configured,
returns a graceful "unavailable" result so the pipeline continues.
"""
from __future__ import annotations

import textwrap
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from app.graph.state import CarAssistantState
from app.schemas.common import SourceInfo


class SandboxAgentOutput(BaseModel):
    agent_name: str = "sandbox"
    executed: bool = False
    code: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    sandbox_id: Optional[str] = None
    sources: list[SourceInfo] = Field(default_factory=list)


async def run_sandbox_agent(state: CarAssistantState) -> SandboxAgentOutput:
    """
    Spawns an ephemeral Daytona sandbox, runs a diagnostic script
    based on the vehicle + issue, and returns the output.
    """
    from app.providers.daytona.client import get_daytona_client

    daytona = get_daytona_client()
    if daytona is None:
        logger.info("sandbox_agent: Daytona not configured, skipping")
        return SandboxAgentOutput(
            error="Daytona not configured (DAYTONA_API_KEY not set)",
        )

    vehicle = state.get("vehicle")
    issue = state.get("issue") or state.get("user_query", "")

    # Build a lightweight diagnostic script based on context
    vehicle_str = (
        f"{vehicle.make} {vehicle.model} {vehicle.year or ''}".strip()
        if vehicle else "Unknown vehicle"
    )

    code = textwrap.dedent(f"""
        # Carlover Diagnostic Script
        # Vehicle: {vehicle_str}
        # Issue: {issue}

        vehicle = {{
            "make": "{vehicle.make if vehicle else 'Unknown'}",
            "model": "{vehicle.model if vehicle else 'Unknown'}",
            "year": {vehicle.year if vehicle and vehicle.year else 'None'},
            "issue": "{issue}",
        }}

        # Basic diagnostic heuristics
        findings = []

        issue_lower = vehicle["issue"].lower()

        if any(w in issue_lower for w in ["quietsch", "squeak", "brake", "bremse"]):
            findings.append({{
                "system": "brakes",
                "severity": "medium",
                "action": "Inspect brake pads and rotors. Replace if worn below 3mm.",
            }})

        if any(w in issue_lower for w in ["motor", "engine", "ruckeln", "stutter"]):
            findings.append({{
                "system": "engine",
                "severity": "high",
                "action": "Check error codes with OBD-II scanner. Inspect ignition system.",
            }})

        if any(w in issue_lower for w in ["öl", "oil", "leak", "leck"]):
            findings.append({{
                "system": "lubrication",
                "severity": "high",
                "action": "Locate leak source. Check seals, gaskets, drain plug.",
            }})

        if any(w in issue_lower for w in ["kühlwasser", "coolant", "überhitz", "overheat"]):
            findings.append({{
                "system": "cooling",
                "severity": "critical",
                "action": "Do not drive. Check coolant level, thermostat, radiator.",
            }})

        if not findings:
            findings.append({{
                "system": "general",
                "severity": "low",
                "action": "Consult a mechanic for a full diagnostic scan.",
            }})

        import json
        print(json.dumps({{"vehicle": vehicle, "findings": findings}}, ensure_ascii=False, indent=2))
    """).strip()

    sandbox_id: Optional[str] = None
    try:
        from daytona_sdk import CreateSandboxFromImageParams

        logger.info("sandbox_agent: creating Daytona sandbox")
        sandbox = daytona.create(
            CreateSandboxFromImageParams(
                image="python:3.12-slim",
                language="python",
                auto_stop_interval=5,      # minutes — ephemeral
                auto_delete_interval=10,   # minutes — clean up after use
            )
        )
        sandbox_id = sandbox.id
        logger.info(f"sandbox_agent: sandbox {sandbox_id} created")

        # Execute the diagnostic script
        response = sandbox.process.code_run(code)
        output = response.result or ""
        exit_code = getattr(response, "exit_code", 0)

        logger.info(f"sandbox_agent: exec done exit_code={exit_code}")

        # Clean up immediately (auto-delete will also handle it)
        try:
            daytona.delete(sandbox)
        except Exception:
            pass

        return SandboxAgentOutput(
            executed=True,
            code=code,
            output=output,
            sandbox_id=sandbox_id,
            sources=[SourceInfo(label="Daytona Sandbox Diagnostic", type="internal", confidence=0.7)],
        )

    except Exception as exc:
        logger.error(f"sandbox_agent failed: {exc}")
        # Attempt cleanup
        if sandbox_id:
            try:
                daytona.delete(daytona.get(sandbox_id))
            except Exception:
                pass
        return SandboxAgentOutput(
            executed=False,
            sandbox_id=sandbox_id,
            error=str(exc),
        )
