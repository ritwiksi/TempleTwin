"""Snowflake Cortex reasoning service for Ask Temple Twin."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import snowflake.connector
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV = PROJECT_ROOT / ".env"

# During local development, prefer the repository .env over stale shell exports.
# Production deployments normally do not ship a .env file, so injected environment
# variables remain the source of truth there.
if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV, override=True)
else:
    load_dotenv()

MODEL = os.getenv("SNOWFLAKE_CORTEX_MODEL", "llama3.1-8b")

_REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_ROLE",
)


class SnowflakeConfigurationError(RuntimeError):
    """Raised when Snowflake credentials/configuration are incomplete."""


def _settings() -> dict[str, str]:
    missing = [name for name in _REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise SnowflakeConfigurationError(
            "Missing Snowflake configuration: " + ", ".join(missing)
        )

    return {name: os.environ[name] for name in _REQUIRED_ENV}


def build_grounded_prompt(question: str, context: dict[str, Any]) -> str:
    """Create a concise prompt that constrains Cortex to Temple Twin context."""
    context_json = json.dumps(context, default=str, indent=2, sort_keys=True)

    return f"""You are Ask Temple Twin, the explanation layer for a university campus
energy digital twin.

Answer questions about Temple Twin and the campus energy digital twin using ONLY the
Temple Twin context below. Relevant topics include building energy use, campus load,
end uses, interventions, rooftop solar, weather, carbon, modeling assumptions, data
sources, calibration, uncertainty, and comparisons supported by the supplied context.

If the user asks something unrelated to Temple Twin or campus energy modeling, briefly
say that you can only answer questions about Temple Twin and its energy model.

Do not invent meter readings, occupancy, equipment, causes, savings, or building facts
that are not present in the context.

Important interpretation rules:
- Building interval values are modeled estimates, not Temple smart-meter readings.
- Annual electricity is building-level reported data only when the context explicitly
  says so; otherwise it is campus-EUI calibrated.
- ComStock supplies simulated 15-minute end-use load shapes.
- Historical weather is from Open-Meteo.
- Carbon uses EPA eGRID.
- If the context is insufficient to establish a cause, say what the data suggests and
  what additional information would be needed.
- Treat fields ending in "_kw" as kilowatts (kW), not watts.
- Never report a zero demand merely because data is missing; if a required value is
  absent, say the context does not contain it.
- Be concise and concrete. Prefer numbers from the context when useful.
- Answer in 2–4 short sentences.
- Keep the response under about 110 words.

TEMPLE TWIN CONTEXT:
{context_json}

USER QUESTION:
{question}
"""


def complete_with_cortex(question: str, context: dict[str, Any]) -> str:
    """Send grounded Temple Twin context to Snowflake Cortex COMPLETE."""
    settings = _settings()
    prompt = build_grounded_prompt(question, context)

    connection = snowflake.connector.connect(
        account=settings["SNOWFLAKE_ACCOUNT"],
        user=settings["SNOWFLAKE_USER"],
        password=settings["SNOWFLAKE_PASSWORD"],
        warehouse=settings["SNOWFLAKE_WAREHOUSE"],
        database=settings["SNOWFLAKE_DATABASE"],
        schema=settings["SNOWFLAKE_SCHEMA"],
        role=settings["SNOWFLAKE_ROLE"],
        session_parameters={
            "QUERY_TAG": "temple_twin_ask",
        },
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                (MODEL, prompt),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if not row or row[0] is None:
        raise RuntimeError("Snowflake Cortex returned an empty response")

    return str(row[0]).strip()



def connection_diagnostics() -> dict[str, Any]:
    """Test Snowflake login/session context and Cortex without exposing secrets."""
    settings = _settings()
    result: dict[str, Any] = {
        "configured": True,
        "account": settings["SNOWFLAKE_ACCOUNT"],
        "user": settings["SNOWFLAKE_USER"],
        "role": settings["SNOWFLAKE_ROLE"],
        "warehouse": settings["SNOWFLAKE_WAREHOUSE"],
        "database": settings["SNOWFLAKE_DATABASE"],
        "schema": settings["SNOWFLAKE_SCHEMA"],
        "model": MODEL,
        "login": False,
        "session": False,
        "cortex": False,
    }

    connection = snowflake.connector.connect(
        account=settings["SNOWFLAKE_ACCOUNT"],
        user=settings["SNOWFLAKE_USER"],
        password=settings["SNOWFLAKE_PASSWORD"],
        warehouse=settings["SNOWFLAKE_WAREHOUSE"],
        database=settings["SNOWFLAKE_DATABASE"],
        schema=settings["SNOWFLAKE_SCHEMA"],
        role=settings["SNOWFLAKE_ROLE"],
        session_parameters={"QUERY_TAG": "temple_twin_diagnostic"},
    )
    result["login"] = True

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE(), "
                "CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
            )
            row = cursor.fetchone()
            if row:
                result["session"] = True
                result["resolved"] = {
                    "account_locator": row[0],
                    "region": row[1],
                    "role": row[2],
                    "warehouse": row[3],
                    "database": row[4],
                    "schema": row[5],
                }

            cursor.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                (MODEL, "Reply with exactly: Temple Twin Cortex OK"),
            )
            cortex_row = cursor.fetchone()
            result["cortex"] = bool(cortex_row and cortex_row[0])
            result["cortex_preview"] = (
                str(cortex_row[0]).strip()[:120]
                if cortex_row and cortex_row[0] is not None
                else None
            )
    finally:
        connection.close()

    return result
