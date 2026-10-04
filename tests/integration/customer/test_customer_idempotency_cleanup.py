import hashlib
import re

from sqlalchemy import create_engine, text

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import INTERNAL_TOKEN
from tests.utils.requisition import ClientRequisition
from tests.utils.db_utils import DbUtils
import os


def _worker_token() -> str:
    return os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")


def _customer_key_from_cpf(document_number: str) -> str:
    """A mesma chave que o servidor deriva do CPF (src/utils/idempotency.py).

    O cadastro não usa mais um header escolhido pelo cliente: a chave de
    idempotência é o SHA-256 dos dígitos do CPF.
    """
    digits = re.sub(r"\D", "", document_number)
    return hashlib.sha256(f"customer:{digits}".encode("utf-8")).hexdigest()


def test_internal_cleanup_removes_old_customer_idempotency_keys():
    payload = PayloadGenerator.create_customer_payload()
    idempotency_key = _customer_key_from_cpf(payload["document_number"])

    status, _ = RequestGenerator.POST_customer(payload)
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
