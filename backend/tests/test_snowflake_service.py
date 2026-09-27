import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.snowflake_service import build_grounded_prompt, complete_with_cortex


def test_grounded_prompt_includes_context_and_non_hallucination_rules():
    prompt = build_grounded_prompt(
        "Why is SERC high?",
        {
            "scope": "building",
            "building": {"name": "SERC"},
            "state": {"demand_kw": 412.0, "hvac_kw": 100.0},
        },
    )

    assert "Why is SERC high?" in prompt
    assert '"demand_kw": 412.0' in prompt
    assert "modeled estimates" in prompt
    assert "Do not invent" in prompt


@patch.dict(
    "os.environ",
    {
        "SNOWFLAKE_ACCOUNT": "example-account",
        "SNOWFLAKE_USER": "example-user",
        "SNOWFLAKE_PASSWORD": "example-password",
        "SNOWFLAKE_WAREHOUSE": "COMPUTE_WH",
        "SNOWFLAKE_DATABASE": "UTIL_DB",
        "SNOWFLAKE_SCHEMA": "PUBLIC",
        "SNOWFLAKE_ROLE": "ACCOUNTADMIN",
        "SNOWFLAKE_CORTEX_MODEL": "llama3.1-8b",
    },
    clear=False,
)
@patch("app.services.snowflake_service.snowflake.connector.connect")
def test_cortex_call_uses_parameterized_sql(mock_connect):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("Grounded answer",)

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    mock_connect.return_value = connection

    answer = complete_with_cortex(
        "What is happening?",
        {"scope": "campus", "campus_demand_kw": 1234.0},
    )

    assert answer == "Grounded answer"
    sql, params = cursor.execute.call_args.args
    assert sql == "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)"
    assert params[0] == "llama3.1-8b"
    assert "campus_demand_kw" in params[1]
    connection.close.assert_called_once()
