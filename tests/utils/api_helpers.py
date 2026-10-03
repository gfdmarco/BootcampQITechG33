import os
from uuid import uuid4

import requests

from tests.utils.payload_generator import PayloadGenerator
from tests.utils.request_generator import INTERNAL_TOKEN, RequestGenerator
from tests.utils.requisition import ClientRequisition


def call(method: str, path: str, token: str = None, payload: dict = None,
         params: dict = None, internal_token: bool = True):
    """Requisição genérica, para rotas que o RequestGenerator não cobre."""
    headers = {}
    if internal_token:
        headers["INTERNAL-TOKEN"] = INTERNAL_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = ClientRequisition.send(method, path, payload=payload,
                                      headers=headers, query_params=params)
    return response.response_status, response.response_json


def new_customer(**overrides):
    """Cria um cliente e faz login. Devolve (customer_key, access_token, payload)."""
    payload = PayloadGenerator.create_customer_payload(**overrides)
    status, body = RequestGenerator.POST_customer(payload)
    assert status == 201, body
    status, login = RequestGenerator.POST_auth_login({
        "document_number": payload["document_number"],
        "password": payload["password"],
    })
    assert status == 200, login
    return body["customer_key"], login["access_token"], payload


def open_account(customer_key: str, token: str, account_type: str = "checking") -> str:
    status, body = RequestGenerator.POST_customer_account(customer_key, {"type": account_type}, token)
    assert status == 201, body
    return body["account_key"]


def deposit(account_key: str, amount: int, token: str) -> str:
    status, body = RequestGenerator.POST_transaction(PayloadGenerator.deposit(account_key, amount), token)
    assert status == 201, body
    return body["transaction_key"]


def transfer(origin: str, destination: str, amount: int, token: str, channel: str = "pix"):
    """Tenta a transferência e devolve (status, corpo) — não assume sucesso."""
    return RequestGenerator.POST_transaction(
        PayloadGenerator.transfer(origin, destination, amount, channel), token
    )


def balance(account_key: str, token: str) -> int:
    status, body = call("GET", f"/accounts/{account_key}/balance", token)
    assert status == 200, body
    return body["balance"]


def get_transaction(transaction_key: str, token: str):
    return call("GET", f"/transactions/{transaction_key}", token)


def random_key() -> str:
    return str(uuid4())


RISK_URL = f"http://{os.environ.get('SERVER_LOCALHOST', '0.0.0.0')}:{os.environ.get('RISK_API_PORT', '8001')}"
RISK_HEADERS = {"INTERNAL-TOKEN": os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")}


def set_risk_score(customer_key: str, score: str) -> None:
    """Define o score do cliente direto no Risk Engine (low / medium / high).

    Cliente novo não tem perfil no Risk Engine de verdade, e o empréstimo cai
    no score "unknown". Testes que dependem dos juros chamam isto antes.
    """
    resp = requests.patch(
        f"{RISK_URL}/risk_profile/{customer_key}",
        json={"score": score, "reason": "Integration Test"},
        headers=RISK_HEADERS,
        timeout=5,
    )
    assert resp.status_code == 200, f"Falha ao definir score '{score}': {resp.text}"