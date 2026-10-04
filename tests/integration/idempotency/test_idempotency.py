"""Idempotência: o mesmo pedido, um efeito só (Dia 4, timeouts e idempotência).

Decisões testadas aqui (ver RFC):
  • Cliente: a chave é derivada do CPF pelo servidor. Repetir o cadastro
    devolve o cliente da primeira vez; mesmo CPF com outros dados → 409
    QIT001004.
  • Conta e transação: a chave vem do cliente no header Idempotency-Key
    (UUID, obrigatório → 400 QIT001028 se faltar). Mesma chave e mesmo
    pedido → devolve o resultado original (201), sem efeito novo. Mesma
    chave com outro pedido, ou de outro cliente → 409 QIT001027.
  • Concorrência: pedidos simultâneos com a mesma chave executam uma vez
    (advisory lock no Postgres + UNIQUE na coluna da chave).
"""
import threading
from uuid import uuid4

from sqlalchemy import create_engine, text

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.api_helpers import balance, call, deposit, new_customer, open_account
from tests.utils.db_utils import DbUtils

_engine = create_engine(DbUtils.database_url())


def db_scalar(sql: str, **params):
    with _engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def run_together(fn, times=5):
    results = []
    threads = [threading.Thread(target=lambda: results.append(fn())) for _ in range(times)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def open_account_with_key(customer_key, token, key, account_type="checking"):
    return call("POST", f"/customers/{customer_key}/accounts", token,
                payload={"type": account_type}, headers={"Idempotency-Key": key})


def transfer_with_key(token, origin, destination, amount, key, channel="pix"):
    return call("POST", "/transactions", token, headers={"Idempotency-Key": key}, payload={
        "type": "transfer", "origin_account_key": origin, "destination_account_key": destination,
        "amount": amount, "channel": channel,
    })


def funded_pair(amount=10_000):
    k1, t1, _ = new_customer()
    a1 = open_account(k1, t1)
    deposit(a1, amount, t1)
    k2, t2, _ = new_customer()
    a2 = open_account(k2, t2)
    return (k1, t1, a1), (k2, t2, a2)


# ── cliente: chave derivada do CPF ───────────────────────────────
class TestCustomerIdempotency:
    def test_same_registration_twice_returns_the_same_customer(self):
        payload = PayloadGenerator.create_customer_payload()

        s1, first = RequestGenerator.POST_customer(payload)
        s2, second = RequestGenerator.POST_customer(payload)

        assert (s1, s2) == (201, 201)
        assert second["customer_key"] == first["customer_key"]
        assert db_scalar("SELECT count(*) FROM customer WHERE document_number = :d",
                         d=payload["document_number"]) == 1

    def test_same_cpf_with_other_password_is_refused(self):
        payload = PayloadGenerator.create_customer_payload()
        RequestGenerator.POST_customer(payload)

        other = dict(payload, password="OutraSenha123")
        status, body = RequestGenerator.POST_customer(other)

        assert status == 409
        assert body["code"] == "QIT001004"

    def test_simultaneous_registrations_create_one_customer(self):
        payload = PayloadGenerator.create_customer_payload()

        results = run_together(lambda: RequestGenerator.POST_customer(payload))

        assert [s for s, _ in results] == [201] * 5, results
        assert len({b["customer_key"] for _, b in results}) == 1
        assert db_scalar("SELECT count(*) FROM customer WHERE document_number = :d",
                         d=payload["document_number"]) == 1

    def test_closed_customer_is_not_replayed(self):
        """Depois de encerrado, o mesmo cadastro não "ressuscita" o cliente antigo."""
        payload = PayloadGenerator.create_customer_payload()
        _, created = RequestGenerator.POST_customer(payload)
        _, login = RequestGenerator.POST_auth_login(
            {"document_number": payload["document_number"], "password": payload["password"]})
        assert RequestGenerator.DELETE_customer(created["customer_key"], login["access_token"])[0] == 204

        status, body = RequestGenerator.POST_customer(payload)

        assert status == 409
        assert body["code"] == "QIT001004"

    def test_cpf_is_not_stored_in_plain_text_as_key(self):
        payload = PayloadGenerator.create_customer_payload()
        _, created = RequestGenerator.POST_customer(payload)
        digits = "".join(c for c in payload["document_number"] if c.isdigit())

        stored = db_scalar(
            "SELECT r.idempotency_key FROM customer_idempotency_request r "
            "JOIN customer c ON c.id = r.customer_id WHERE c.customer_key = :k",
            k=created["customer_key"])

        assert len(stored) == 64                      # SHA-256 em hexadecimal
        assert digits not in stored


# ── conta: chave enviada pelo cliente ────────────────────────────
class TestAccountIdempotency:
    def test_missing_or_invalid_key_is_400(self):
        key, token, _ = new_customer()

        for header in (None, "nao-e-uuid"):
            status, body = open_account_with_key(key, token, header)
            assert status == 400, header
            assert body["code"] == "QIT001028"

        status, accounts = RequestGenerator.GET_accounts(token)
        assert accounts["data"] == []

    def test_retry_returns_the_same_account(self):
        key, token, _ = new_customer()
        idem = str(uuid4())

        s1, first = open_account_with_key(key, token, idem)
        s2, second = open_account_with_key(key, token, idem)

        assert (s1, s2) == (201, 201)
        assert second["account_key"] == first["account_key"]
        _, accounts = RequestGenerator.GET_accounts(token)
        assert len(accounts["data"]) == 1

    def test_same_key_other_type_is_409(self):
        key, token, _ = new_customer()
        idem = str(uuid4())
        open_account_with_key(key, token, idem, "checking")

        status, body = open_account_with_key(key, token, idem, "savings")

        assert status == 409
        assert body["code"] == "QIT001027"

    def test_other_customer_cannot_reuse_my_key(self):
        alice_key, alice_token, _ = new_customer()
        bob_key, bob_token, _ = new_customer()
        idem = str(uuid4())
        _, alice_account = open_account_with_key(alice_key, alice_token, idem)

        status, body = open_account_with_key(bob_key, bob_token, idem)

        assert status == 409
        assert "account_key" not in body              # não vaza a conta da Alice

    def test_simultaneous_retries_open_one_account(self):
        key, token, _ = new_customer()
        idem = str(uuid4())

        results = run_together(lambda: open_account_with_key(key, token, idem))

        assert [s for s, _ in results] == [201] * 5, results
        assert len({b["account_key"] for _, b in results}) == 1
        _, accounts = RequestGenerator.GET_accounts(token)
        assert len(accounts["data"]) == 1

    def test_retry_of_the_fifth_account_is_not_blocked_by_the_limit(self):
        key, token, _ = new_customer()
        for _ in range(4):
            open_account(key, token)
        idem = str(uuid4())
        assert open_account_with_key(key, token, idem)[0] == 201

        status, _ = open_account_with_key(key, token, idem)

        assert status == 201                          # é a mesma conta, não a 6ª


# ── transação: chave enviada pelo cliente ────────────────────────
class TestTransactionIdempotency:
    def test_missing_key_is_400_and_nothing_moves(self):
        (_, t1, a1), (_, t2, a2) = funded_pair()

        status, body = transfer_with_key(t1, a1, a2, 1_000, None)

        assert status == 400
        assert body["code"] == "QIT001028"
        assert balance(a1, t1) == 10_000

    def test_retry_returns_the_same_transfer_and_debits_once(self):
        (_, t1, a1), (_, t2, a2) = funded_pair()
        idem = str(uuid4())

        s1, first = transfer_with_key(t1, a1, a2, 1_000, idem)
        s2, second = transfer_with_key(t1, a1, a2, 1_000, idem)

        assert (s1, s2) == (201, 201)
        assert second["transaction_key"] == first["transaction_key"]
        assert balance(a1, t1) == 9_000
        assert balance(a2, t2) == 1_000

    def test_same_key_other_amount_is_409_and_nothing_moves(self):
        (_, t1, a1), (_, t2, a2) = funded_pair()
        idem = str(uuid4())
        transfer_with_key(t1, a1, a2, 1_000, idem)

        status, body = transfer_with_key(t1, a1, a2, 2_000, idem)

        assert status == 409
        assert body["code"] == "QIT001027"
        assert balance(a1, t1) == 9_000

    def test_other_customer_cannot_reuse_my_key(self):
        (_, t1, a1), (k2, t2, a2) = funded_pair()
        deposit(a2, 10_000, t2)
        idem = str(uuid4())
        transfer_with_key(t1, a1, a2, 1_000, idem)

        status, body = transfer_with_key(t2, a2, a1, 1_000, idem)

        assert status == 409
        assert balance(a2, t2) == 11_000

    def test_simultaneous_retries_debit_once(self):
        """Clique duplo / retry após timeout: 5 pedidos iguais ao mesmo tempo."""
        (_, t1, a1), (_, t2, a2) = funded_pair()
        idem = str(uuid4())

        results = run_together(lambda: transfer_with_key(t1, a1, a2, 1_000, idem))

        assert [s for s, _ in results] == [201] * 5, results
        assert len({b["transaction_key"] for _, b in results}) == 1
        assert balance(a1, t1) == 9_000
        assert balance(a2, t2) == 1_000

    def test_deposit_retry_credits_once(self):
        key, token, _ = new_customer()
        account = open_account(key, token)
        idem = str(uuid4())
        payload = {"type": "deposit", "destination_account_key": account, "amount": 500, "channel": "pix"}

        for _ in range(3):
            assert call("POST", "/transactions", token, payload=payload,
                        headers={"Idempotency-Key": idem})[0] == 201

        assert balance(account, token) == 500

    def test_different_keys_are_different_transfers(self):
        """Duas transferências iguais com chaves diferentes são legítimas."""
        (_, t1, a1), (_, t2, a2) = funded_pair()

        transfer_with_key(t1, a1, a2, 1_000, str(uuid4()))
        transfer_with_key(t1, a1, a2, 1_000, str(uuid4()))

        assert balance(a1, t1) == 8_000
