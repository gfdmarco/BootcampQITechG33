import os
from uuid import uuid4

import requests
from sqlalchemy import create_engine, text


def _localhost(value: str) -> str:
    return "127.0.0.1" if value in ("", "0.0.0.0") else value


RISK_HOST = _localhost(os.environ.get("SERVER_LOCALHOST", "0.0.0.0"))
RISK_PORT = os.environ.get("RISK_API_PORT", "8001")
RISK_URL = f"http://{RISK_HOST}:{RISK_PORT}"
RISK_TOKEN = os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")
RISK_HEADERS = {"INTERNAL-TOKEN": RISK_TOKEN}


def _risk_database_url() -> str:
    risk_db_port = os.environ.get("RISK_DB_PORT", "5433")
    url = os.environ.get(
        "RISK_DATABASE_URL",
        f"postgresql+psycopg2://risk:risk@localhost:{risk_db_port}/risk",
    )
    return url.replace("@localhost:", "@127.0.0.1:")


def _risk_conn():
    engine = create_engine(_risk_database_url())
    return engine, engine.connect()


def _set_score(customer_key: str, score: str, reason: str = "test") -> None:
    response = requests.patch(
        f"{RISK_URL}/risk_profile/{customer_key}",
        json={"score": score, "reason": reason},
        headers=RISK_HEADERS,
        timeout=5,
    )
    assert response.status_code == 200, response.text


def _evaluate(customer_key: str, evaluation_key: str, amount: int = 1_000_000):
    response = requests.post(
        f"{RISK_URL}/evaluate",
        json={
            "evaluation_key": evaluation_key,
            "customer_key": customer_key,
            "amount": amount,
            "transaction_type": "pix",
        },
        headers=RISK_HEADERS,
        timeout=5,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestRiskEvaluationState:
    def test_profile_update_writes_immutable_event_history(self):
        customer_key = str(uuid4())

        _set_score(customer_key, "low", "first score")
        _set_score(customer_key, "medium", "score changed")

        engine, connection = _risk_conn()
        try:
            rows = connection.execute(
                text(
                    """
                    SELECT from_status.enumerator AS from_score,
                           to_status.enumerator AS to_score,
                           event.reason
                      FROM risk_evaluation_event event
                      LEFT JOIN risk_score_status from_status
                        ON from_status.id = event.from_score_id
                      JOIN risk_score_status to_status
                        ON to_status.id = event.to_score_id
                     WHERE event.customer_key = :customer_key
                     ORDER BY event.id
                    """
                ),
                {"customer_key": customer_key},
            ).mappings().all()
        finally:
            connection.close()
            engine.dispose()

        assert len(rows) == 2
        assert rows[0]["from_score"] is None
        assert rows[0]["to_score"] == "low"
        assert rows[1]["from_score"] == "low"
        assert rows[1]["to_score"] == "medium"

    def test_evaluate_is_idempotent_for_same_evaluation_key(self):
        customer_key = str(uuid4())
        evaluation_key = str(uuid4())

        _set_score(customer_key, "medium", "daily limit test")

        first = _evaluate(customer_key, evaluation_key)
        duplicate = _evaluate(customer_key, evaluation_key)
        third = _evaluate(customer_key, str(uuid4()))

        assert first["action"] == "APPROVE"
        assert duplicate == first
        assert third["action"] == "APPROVE"

        denied = _evaluate(customer_key, str(uuid4()))
        assert denied["action"] == "DENY"
        assert "DAILY_LIMIT_EXCEEDED" in denied["reason"]

        engine, connection = _risk_conn()
        try:
            consumption_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                      FROM risk_limit_consumption
                     WHERE customer_key = :customer_key
                       AND transaction_type = 'pix'
                       AND amount = 1000000
                    """
                ),
                {"customer_key": customer_key},
            ).scalar_one()
        finally:
            connection.close()
            engine.dispose()

        assert consumption_count == 2
