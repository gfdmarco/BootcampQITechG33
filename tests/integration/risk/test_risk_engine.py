import requests
import os

from tests.utils import PayloadGenerator, RequestGenerator

RISK_API_HOST  = os.environ.get("SERVER_LOCALHOST", "0.0.0.0")
RISK_API_PORT  = os.environ.get("RISK_API_PORT", "8001")
RISK_URL       = f"http://{RISK_API_HOST}:{RISK_API_PORT}"
RISK_TOKEN     = os.environ.get("RISK_INTERNAL_TOKEN", "risk_default_token")
RISK_HEADERS   = {"INTERNAL-TOKEN": RISK_TOKEN}


def _setup_customer_with_account_and_balance(balance: int):
    """Helper: cria cliente → conta → deposita saldo. Retorna (customer_key, access_token, account_key)."""
    customer_payload = PayloadGenerator.create_customer_payload()
    _, customer_resp = RequestGenerator.POST_customer(customer_payload)
    customer_key = customer_resp["customer_key"]

    _, login_resp = RequestGenerator.POST_auth_login({
        "document_number": customer_payload["document_number"],
        "password":         customer_payload["password"],
    })
    access_token = login_resp["access_token"]

    _, acc_resp = RequestGenerator.POST_customer_account(
        customer_key, {"type": "checking"}, access_token
    )
    account_key = acc_resp["account_key"]

    if balance > 0:
        status, _ = RequestGenerator.POST_transaction({
            "destination_account_key": account_key,
            "type":    "deposit",
            "channel": "pix",
            "amount":  balance,
        }, access_token)
        assert status == 201, f"Falha ao depositar saldo inicial: {balance}"

    return customer_key, access_token, account_key


def _set_risk_score(customer_key: str, score: str) -> None:
    resp = requests.patch(
        f"{RISK_URL}/risk_profile/{customer_key}",
        json={"score": score, "reason": "Integration Test"},
        headers=RISK_HEADERS,
    )
    assert resp.status_code == 200, f"Falha ao definir score '{score}': {resp.text}"


class TestRiskPerTxLimit:
    """Limite por transação individual."""

    def test_high_score_blocks_transaction_above_limit(self):
        """Score HIGH → transação acima de R$1k é recusada com 403."""
        alice_key, alice_token, alice_acc = _setup_customer_with_account_and_balance(500_000)
        _, _, bob_acc = _setup_customer_with_account_and_balance(0)

        _set_risk_score(alice_key, "high")

        # R$2k > limite HIGH de R$1k → deve bloquear
        status, response = RequestGenerator.POST_transaction({
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  200_000,
        }, alice_token)

        assert status == 403, f"Esperado 403, recebeu {status}: {response}"

    def test_high_score_allows_transaction_below_limit(self):
        """Score HIGH → transação abaixo de R$1k é aprovada."""
        alice_key, alice_token, alice_acc = _setup_customer_with_account_and_balance(500_000)
        _, _, bob_acc = _setup_customer_with_account_and_balance(0)

        _set_risk_score(alice_key, "high")

        # R$500 < limite HIGH de R$1k → deve aprovar
        status, response = RequestGenerator.POST_transaction({
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  50_000,
        }, alice_token)

        assert status == 201, f"Esperado 201, recebeu {status}: {response}"

    def test_low_score_allows_large_transaction(self):
        """Score LOW → transação de alto valor deve ser aprovada (sem restrição)."""
        alice_key, alice_token, alice_acc = _setup_customer_with_account_and_balance(2_000_000)
        _, _, bob_acc = _setup_customer_with_account_and_balance(0)

        _set_risk_score(alice_key, "low")

        # R$10k — sem restrição para LOW
        status, response = RequestGenerator.POST_transaction({
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  1_000_000,
        }, alice_token)

        assert status == 201, f"Esperado 201, recebeu {status}: {response}"


class TestRiskDailyLimit:
    """Limite diário acumulado via Redis."""

    def test_medium_score_daily_limit_is_enforced(self):
        """
        Score MEDIUM → limite diário de R$20k (2_000_000 centavos).
        Duas transferências de R$10k devem passar; a terceira deve ser bloqueada.
        """
        alice_key, alice_token, alice_acc = _setup_customer_with_account_and_balance(5_000_000)
        _, _, bob_acc = _setup_customer_with_account_and_balance(0)

        _set_risk_score(alice_key, "medium")

        tx_payload = {
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  1_000_000,  # R$10k — dentro do limite por tx
        }

        # Primeira: deve passar (acumulado R$10k)
        status, _ = RequestGenerator.POST_transaction(tx_payload, alice_token)
        assert status == 201, "Primeira transferência de R$10k deveria passar"

        # Segunda: deve passar (acumulado R$20k, exatamente no limite)
        status, _ = RequestGenerator.POST_transaction(tx_payload, alice_token)
        assert status == 201, "Segunda transferência de R$10k deveria passar"

        # Terceira: deve ser bloqueada (acumulado R$30k > diário R$20k)
        status, response = RequestGenerator.POST_transaction(tx_payload, alice_token)
        assert status == 403, f"Terceira transferência deveria ser bloqueada pelo limite diário, recebeu {status}: {response}"


class TestRiskScoreUpgrade:
    """Transição de score reflete imediatamente (Redis invalidation)."""

    def test_profile_upgrade_from_high_to_low_unlocks_large_transfer(self):
        """
        Cliente HIGH tem transferência bloqueada.
        Após upgrade para LOW, a mesma transferência é aprovada.
        """
        alice_key, alice_token, alice_acc = _setup_customer_with_account_and_balance(500_000)
        _, _, bob_acc = _setup_customer_with_account_and_balance(0)

        _set_risk_score(alice_key, "high")

        # Bloqueado em HIGH
        status, _ = RequestGenerator.POST_transaction({
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  200_000,
        }, alice_token)
        assert status == 403

        # Upgrade para LOW
        _set_risk_score(alice_key, "low")

        # Agora deve passar
        status, response = RequestGenerator.POST_transaction({
            "origin_account_key":      alice_acc,
            "destination_account_key": bob_acc,
            "type":    "transfer",
            "channel": "pix",
            "amount":  200_000,
        }, alice_token)
        assert status == 201, f"Após upgrade para LOW, esperado 201: {response}"
