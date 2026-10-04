import sys
import types
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
redis_stub = types.SimpleNamespace(
    Redis=object,
    RedisError=Exception,
    from_url=lambda *args, **kwargs: None,
)
sys.modules.setdefault("redis", redis_stub)

from connectors.risk_engine_connector import RiskEngineConnector
from errors import RiskEngineDenied


def test_evaluate_transaction_denies_when_risk_times_out(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("risk timeout")

    monkeypatch.setattr(requests, "post", timeout)

    connector = RiskEngineConnector()

    with pytest.raises(RiskEngineDenied) as error:
        connector.evaluate_transaction(
            customer_key="customer-key",
            amount=1,
            transaction_type="pix",
            evaluation_key="evaluation-key",
        )

    assert "timed out" in error.value.description


def test_evaluate_transaction_denies_unexpected_risk_status(monkeypatch):
    class Response:
        status_code = 503
        text = "service unavailable"

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())

    connector = RiskEngineConnector()

    with pytest.raises(RiskEngineDenied) as error:
        connector.evaluate_transaction(
            customer_key="customer-key",
            amount=1,
            transaction_type="pix",
            evaluation_key="evaluation-key",
        )

    assert "unexpected response" in error.value.description
