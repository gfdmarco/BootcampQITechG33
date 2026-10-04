"""Empréstimo idempotente pela requisição, no mesmo modelo da transferência.

POST /loans exige o header Idempotency-Key (UUID). A mesma chave com o
mesmo pedido devolve o mesmo empréstimo, sem crédito novo; com outro
pedido (ou de outro cliente), 409 QIT001027. Sem chave, 400 QIT001028.
"""
import threading
from uuid import uuid4

from tests.utils.api_helpers import balance, call, new_customer, open_account, set_risk_score


def customer_with_account():
    key, token, _ = new_customer()
    account = open_account(key, token)
    set_risk_score(key, "low")
    return token, account


def take_loan(token, account, amount, installments, key):
    return call("POST", "/loans", token, headers={"Idempotency-Key": key},
                payload={"account_key": account, "requested_amount": amount, "installments_count": installments})


class TestLoanIdempotency:
    def test_missing_key_is_400_and_no_money_enters(self):
        token, account = customer_with_account()

        status, body = take_loan(token, account, 100_000, 3, None)

        assert status == 400
        assert body["code"] == "QIT001028"
        assert balance(account, token) == 0

    def test_retry_returns_the_same_loan_and_credits_once(self):
        token, account = customer_with_account()
        idem = str(uuid4())

        s1, first = take_loan(token, account, 100_000, 3, idem)
        s2, second = take_loan(token, account, 100_000, 3, idem)

        assert (s1, s2) == (201, 201)
        assert second["loan_key"] == first["loan_key"]
        assert [i["id"] for i in second["installments"]] == [i["id"] for i in first["installments"]]
        assert balance(account, token) == 100_000

    def test_same_key_other_amount_is_409(self):
        token, account = customer_with_account()
        idem = str(uuid4())
        take_loan(token, account, 100_000, 3, idem)

        status, body = take_loan(token, account, 200_000, 3, idem)

        assert status == 409
        assert body["code"] == "QIT001027"
        assert balance(account, token) == 100_000

    def test_other_customer_cannot_reuse_my_key(self):
        token, account = customer_with_account()
        other_token, other_account = customer_with_account()
        idem = str(uuid4())
        take_loan(token, account, 100_000, 3, idem)

        status, body = take_loan(other_token, other_account, 100_000, 3, idem)

        assert status == 409
        assert "loan_key" not in body
        assert balance(other_account, other_token) == 0

    def test_simultaneous_retries_create_one_loan(self):
        token, account = customer_with_account()
        idem = str(uuid4())
        results = []

        threads = [threading.Thread(target=lambda: results.append(take_loan(token, account, 100_000, 3, idem)))
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert [s for s, _ in results] == [201] * 5, results
        assert len({b["loan_key"] for _, b in results}) == 1
        assert balance(account, token) == 100_000

    def test_different_keys_are_different_loans(self):
        token, account = customer_with_account()

        take_loan(token, account, 100_000, 3, str(uuid4()))
        take_loan(token, account, 100_000, 3, str(uuid4()))

        assert balance(account, token) == 200_000
