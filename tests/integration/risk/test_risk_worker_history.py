"""O LLM Worker precisa enxergar o histórico do cliente.

Antes, o worker chamava /accounts e /statement sem JWT, o Core recusava
e o LLM classificava todo mundo como "Nenhuma transação encontrada".
Agora ele lê /internal/customers/{key}/transactions, protegida por um
segundo segredo (RISK-WORKER-TOKEN = RISK_INTERNAL_TOKEN).

O último teste roda o worker DE VERDADE (Core + Risk Engine reais) e só
troca a chamada ao Groq por uma resposta fixa — assim não depende de
internet nem de chave de API.
"""
import os
import sys

import requests

from tests.utils.api_helpers import call, deposit, new_customer, open_account, transfer
from tests.utils.request_generator import INTERNAL_TOKEN

RISK_TOKEN = os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")
HOST = os.environ.get("SERVER_LOCALHOST", "0.0.0.0")
CORE_URL = f"http://{HOST}:{os.environ.get('API_PORT', '3000')}"
RISK_URL = f"http://{HOST}:{os.environ.get('RISK_API_PORT', '8001')}"


def history(customer_key, worker_token=RISK_TOKEN, params=None):
    headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
    if worker_token is not None:
        headers["RISK-WORKER-TOKEN"] = worker_token
    resp = requests.get(f"{CORE_URL}/internal/customers/{customer_key}/transactions",
                        headers=headers, params=params, timeout=5)
    return resp.status_code, resp.json()


def customer_with_movement():
    """Alice: 2 contas, 1 depósito, 1 transferência enviada, 1 recebida."""
    alice_key, alice_token, _ = new_customer()
    acc1 = open_account(alice_key, alice_token)
    acc2 = open_account(alice_key, alice_token)
    deposit(acc1, 50_000, alice_token)

    bob_key, bob_token, _ = new_customer()
    bob_acc = open_account(bob_key, bob_token)
    deposit(bob_acc, 50_000, bob_token)

    transfer(acc1, bob_acc, 1_000, alice_token)       # Alice envia
    transfer(bob_acc, acc2, 2_000, bob_token)         # Alice recebe (na outra conta)
    return alice_key, bob_key


class TestInternalHistoryRoute:
    def test_without_worker_token_is_forbidden(self):
        """O INTERNAL-TOKEN sozinho não basta: todo cliente da API também tem ele."""
        alice_key, _ = customer_with_movement()

        status, _ = history(alice_key, worker_token=None)

        assert status == 403

    def test_wrong_worker_token_is_forbidden(self):
        alice_key, _ = customer_with_movement()

        status, _ = history(alice_key, worker_token="chute")

        assert status == 403

    def test_client_jwt_does_not_open_the_internal_route(self):
        """Um cliente logado não lê o histórico de outro pela rota interna."""
        alice_key, _ = customer_with_movement()
        _, mallory_token, _ = new_customer()

        status, _ = call("GET", f"/internal/customers/{alice_key}/transactions", mallory_token)

        assert status == 403

    def test_returns_sent_and_received_from_all_accounts(self):
        alice_key, _ = customer_with_movement()

        status, body = history(alice_key)

        assert status == 200, body
        amounts = sorted(t["amount"] for t in body["transactions"])
        assert amounts == [1_000, 2_000, 50_000]
        for t in body["transactions"]:
            assert {"type", "channel", "amount", "fee_amount", "created_at"} <= t.keys()

    def test_does_not_leak_other_customers_transactions(self):
        alice_key, bob_key = customer_with_movement()

        _, body = history(alice_key)

        # o depósito de 50.000 do Bob não aparece no histórico da Alice
        assert [t["amount"] for t in body["transactions"]].count(50_000) == 1

    def test_limit_is_respected(self):
        alice_key, _ = customer_with_movement()

        _, body = history(alice_key, params={"limit": "2"})

        assert len(body["transactions"]) == 2

    def test_unknown_customer_is_404(self):
        status, _ = history("00000000-0000-4000-8000-000000000000")

        assert status == 404

    def test_invalid_params_are_400(self):
        alice_key, _ = customer_with_movement()

        for params in ({"days": "0"}, {"days": "365"}, {"limit": "abc"}, {"outra": "1"}):
            status, _ = history(alice_key, params=params)
            assert status == 400, params


class TestWorkerEndToEnd:
    def test_worker_reads_history_and_updates_score(self, monkeypatch):
        alice_key, _ = customer_with_movement()
        # a transferência da Alice passou pelo /evaluate e criou o perfil "unknown"
        resp = requests.get(f"{RISK_URL}/risk_profile/{alice_key}",
                            headers={"INTERNAL-TOKEN": RISK_TOKEN}, timeout=5)
        assert resp.status_code == 200 and resp.json()["score"] == "unknown"

        # o worker lê a configuração do ambiente ao ser importado
        monkeypatch.setenv("GROQ_API_KEY", "teste-sem-groq")
        monkeypatch.setenv("CORE_API_URL", CORE_URL)
        monkeypatch.setenv("RISK_ENGINE_URL", RISK_URL)
        monkeypatch.setenv("INTERNAL_TOKEN", RISK_TOKEN)
        monkeypatch.setenv("CORE_INTERNAL_TOKEN", INTERNAL_TOKEN)
        risk_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "risk_engine"))
        monkeypatch.syspath_prepend(risk_root)
        sys.modules.pop("worker.llm_classifier", None)
        from worker import llm_classifier

        seen = {}

        def fake_llm(self, history_summary, n):
            seen["summary"], seen["n"] = history_summary, n
            return "medium"

        monkeypatch.setattr(llm_classifier.LLMClassifier, "_classify_with_llm", fake_llm)
        # roda só para a Alice (o banco de teste tem centenas de perfis)
        monkeypatch.setattr(llm_classifier.LLMClassifier, "_fetch_customers_to_evaluate",
                            lambda self: [alice_key])

        llm_classifier.LLMClassifier().run()

        assert seen["n"] == 3, seen                       # o LLM recebeu as 3 transações
        assert "Nenhuma transação" not in seen["summary"]
        resp = requests.get(f"{RISK_URL}/risk_profile/{alice_key}",
                            headers={"INTERNAL-TOKEN": RISK_TOKEN}, timeout=5)
        assert resp.json()["score"] == "medium"