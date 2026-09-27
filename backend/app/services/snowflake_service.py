"""Snowflake Cortex reasoning service for Ask Temple Twin."""

from __future__ import annotations

import json
import os
from typing import Any

import snowflake.connector
from dotenv import load_dotenv

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

Answer the user's question using ONLY the Temple Twin context below.
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
