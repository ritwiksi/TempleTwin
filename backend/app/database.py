"""Tiger Cloud database access.

DATABASE_URL must be a PostgreSQL/Tiger Cloud connection string with SSL,
for example:
postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load the repo-root .env automatically for local development/scripts.
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Add it to the repo-root .env file "
            "or export it in your shell."
        )
    return url


@contextmanager
def get_connection():
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def check_connection() -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            return bool(row and row["ok"] == 1)
