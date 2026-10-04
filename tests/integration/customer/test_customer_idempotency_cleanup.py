from uuid import uuid4

from sqlalchemy import create_engine, text

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import INTERNAL_TOKEN
from tests.utils.requisition import ClientRequisition
from tests.utils.db_utils import DbUtils
import os


def _worker_token() -> str:
    return os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")


def test_internal_cleanup_removes_old_customer_idempotency_keys():
    payload = PayloadGenerator.create_customer_payload()
    idempotency_key = str(uuid4())

    status, _ = RequestGenerator.POST_customer(payload, idempotency_key=idempotency_key)
    assert status == 201

    engine = create_engine(DbUtils.database_url())
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE customer_idempotency_request
                   SET created_at = NOW() - INTERVAL '10 days'
                 WHERE idempotency_key = :idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        )

    response = ClientRequisition.send(
        "POST",
        "/internal/customers/idempotency/cleanup?retention_days=7",
        headers={
            "INTERNAL-TOKEN": INTERNAL_TOKEN,
            "RISK-WORKER-TOKEN": _worker_token(),
        },
    )

    assert response.response_status == 200, response.response_json
    assert response.response_json["deleted_count"] >= 1

    with engine.connect() as connection:
        count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                  FROM customer_idempotency_request
                 WHERE idempotency_key = :idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).scalar_one()
    engine.dispose()

    assert count == 0
