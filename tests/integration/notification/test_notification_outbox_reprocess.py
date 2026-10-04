import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from tests.utils.db_utils import DbUtils
from tests.utils.request_generator import INTERNAL_TOKEN
from tests.utils.requisition import ClientRequisition


def _worker_token() -> str:
    return os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")


def test_internal_reprocesses_pending_notification_outbox():
    event_key = f"test:{uuid4()}"
    customer_key = str(uuid4())

    engine = create_engine(DbUtils.database_url())
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO notification_outbox (
                    event_key,
                    customer_key,
                    title,
                    body,
                    status
                ) VALUES (
                    :event_key,
                    :customer_key,
                    'Teste',
                    'Mensagem pendente',
                    'pending'
                )
                """
            ),
            {"event_key": event_key, "customer_key": customer_key},
        )

    response = ClientRequisition.send(
        "POST",
        "/internal/notifications/reprocess?limit=10",
        headers={
            "INTERNAL-TOKEN": INTERNAL_TOKEN,
            "RISK-WORKER-TOKEN": _worker_token(),
        },
    )

    assert response.response_status == 200, response.response_json
    assert response.response_json["processed_count"] >= 1

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT outbox.status,
                       notification.key
                  FROM notification_outbox outbox
                  JOIN notification
                    ON notification.event_key = outbox.event_key
                 WHERE outbox.event_key = :event_key
                """
            ),
            {"event_key": event_key},
        ).mappings().one()
    engine.dispose()

    assert row["status"] == "processed"
    assert row["key"] is not None
