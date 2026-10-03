"""Regras de empréstimo que os testes originais não cobriam.

Os testes falam com a API de verdade e com o Risk Engine de verdade
(porta 8001). O score do cliente é definido pelo próprio teste, via
PATCH no Risk Engine — assim o resultado não depende de mock nenhum.
"""
import threading

from tests.utils import RequestGenerator
from tests.utils.api_helpers import balance, call, deposit, new_customer, open_account, set_risk_score


# ── auxiliares ───────────────────────────────────────────────────
def customer_with_account(score: str = "low"):
    customer_key, token, _ = new_customer()
    account_key = open_account(customer_key, token)
    set_risk_score(customer_key, score)
    return customer_key, token, account_key


def simulate(account_key, token, amount, installments):
    return call("POST", "/loans/simulate", token,
                payload={"account_key": account_key, "requested_amount": amount, "installments_count": installments})


def take_loan(account_key, token, amount, installments):
    return call("POST", "/loans", token,
                payload={"account_key": account_key, "requested_amount": amount, "installments_count": installments})


def pay(loan_key, installment_id, token):
    return call("POST", f"/loans/{loan_key}/installments/{installment_id}/pay", token)


# ── simulação: juros por score ───────────────────────────────────
class TestLoanInterestByScore:
    def test_low_score_pays_1_5_percent(self):
        _, token, account_key = customer_with_account("low")

        status, body = simulate(account_key, token, 100000, 3)

        assert status == 200, body
        assert body["interest_rate"] == 15                 # décimos de %: 15 = 1,5%
        assert body["total_amount_due"] == 101500
        # a soma das parcelas fecha exatamente com o total (o resto vai na última)
        assert sum(i["amount"] for i in body["installments"]) == 101500

    def test_medium_score_pays_3_percent(self):
        _, token, account_key = customer_with_account("medium")

        status, body = simulate(account_key, token, 100000, 4)

        assert status == 200, body
        assert body["interest_rate"] == 30
        assert body["total_amount_due"] == 103000
        assert sum(i["amount"] for i in body["installments"]) == 103000

    def test_high_score_is_denied_and_no_money_enters(self):
        _, token, account_key = customer_with_account("high")

        status, body = take_loan(account_key, token, 100000, 3)

        assert status == 422, body
        assert balance(account_key, token) == 0

    def test_simulation_does_not_move_money(self):
        _, token, account_key = customer_with_account("low")

        simulate(account_key, token, 100000, 3)

        assert balance(account_key, token) == 0


# ── contrato de entrada ──────────────────────────────────────────
class TestLoanInput:
    def test_refuses_invalid_amount_and_installments(self):
        _, token, account_key = customer_with_account("low")

        for amount, installments in [(0, 3), (-100, 3), (100000, 0), ("100", 3), (100000, "3")]:
            status, _ = take_loan(account_key, token, amount, installments)
            assert status == 400, (amount, installments)

        assert balance(account_key, token) == 0

    def test_refuses_absurd_installment_count(self):
        """Sem limite, um único pedido poderia criar um milhão de parcelas no banco."""
        _, token, account_key = customer_with_account("low")

        status, _ = simulate(account_key, token, 100000, 1000)

        assert status == 400

    def test_refuses_absurd_amount(self):
        """Sem teto, qualquer cliente low pede R$ 1 bilhão e recebe na hora."""
        _, token, account_key = customer_with_account("low")

        status, _ = take_loan(account_key, token, 100_000_000_000, 12)

        assert status == 400
        assert balance(account_key, token) == 0


# ── acesso ───────────────────────────────────────────────────────
class TestLoanAccess:
    def test_other_customers_account_is_forbidden(self):
        _, _, alice_account = customer_with_account("low")
        _, bob_token, _ = new_customer()

        status, _ = take_loan(alice_account, bob_token, 100000, 3)

        assert status == 403

    def test_unknown_account_is_404(self):
        _, token, _ = customer_with_account("low")

        status, _ = take_loan("00000000-0000-4000-8000-000000000000", token, 100000, 3)

        assert status == 404

    def test_requires_login(self):
        _, _, account_key = customer_with_account("low")

        status, _ = take_loan(account_key, None, 100000, 3)

        assert status == 401

    def test_blocked_account_cannot_take_loan(self):
        _, token, account_key = customer_with_account("low")
        RequestGenerator.PUT_account(account_key, {"status": "blocked"}, token)

        status, _ = take_loan(account_key, token, 100000, 3)

        assert status == 403
        assert balance(account_key, token) == 0


# ── contratação ──────────────────────────────────────────────────
class TestLoanDisbursement:
    def test_loan_credits_account_and_shows_in_statement(self):
        """Saldo que muda sem lançamento no extrato é dinheiro sem explicação."""
        _, token, account_key = customer_with_account("low")

        status, loan = take_loan(account_key, token, 100000, 3)

        assert status == 201, loan
        assert balance(account_key, token) == 100000

        status, statement = RequestGenerator.GET_account_statement(account_key, None, token)
        assert status == 200
        assert [t["amount"] for t in statement["data"]] == [100000]

    def test_installments_are_created_pending(self):
        _, token, account_key = customer_with_account("low")

        _, loan = take_loan(account_key, token, 100000, 3)

        assert [i["installment_number"] for i in loan["installments"]] == [1, 2, 3]
        assert {i["status"] for i in loan["installments"]} == {"pending"}
        assert sum(i["amount"] for i in loan["installments"]) == loan["total_amount_due"]


# ── pagamento de parcelas ────────────────────────────────────────
class TestInstallmentPayment:
    def test_paying_debits_exactly_the_installment(self):
        _, token, account_key = customer_with_account("low")
        _, loan = take_loan(account_key, token, 100000, 3)
        first = loan["installments"][0]

        status, _ = pay(loan["loan_key"], first["id"], token)

        assert status == 204
        assert balance(account_key, token) == 100000 - first["amount"]

    def test_paying_the_same_installment_twice_charges_once(self):
        _, token, account_key = customer_with_account("low")
        _, loan = take_loan(account_key, token, 100000, 3)
        first = loan["installments"][0]

        assert pay(loan["loan_key"], first["id"], token)[0] == 204
        status, _ = pay(loan["loan_key"], first["id"], token)

        assert status == 404                               # não está mais pendente
        assert balance(account_key, token) == 100000 - first["amount"]

    def test_simultaneous_payments_charge_once(self):
        """O app manda o mesmo pagamento 5 vezes (clique duplo, retry): debita uma vez."""
        _, token, account_key = customer_with_account("low")
        _, loan = take_loan(account_key, token, 100000, 3)
        first = loan["installments"][0]

        results = []
        threads = [threading.Thread(target=lambda: results.append(pay(loan["loan_key"], first["id"], token)[0]))
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(204) == 1, results
        assert balance(account_key, token) == 100000 - first["amount"]

    def test_insufficient_balance_keeps_installment_pending(self):
        customer_key, token, account_key = customer_with_account("low")
        _, loan = take_loan(account_key, token, 100000, 2)

        # gasta quase tudo: sobra menos que uma parcela
        other_key, other_token, _ = new_customer()
        other_account = open_account(other_key, other_token)
        status, _ = call("POST", "/transactions", token, payload={
            "origin_account_key": account_key, "destination_account_key": other_account,
            "amount": 99000, "type": "transfer", "channel": "pix",
        })
        assert status == 201

        first = loan["installments"][0]
        status, _ = pay(loan["loan_key"], first["id"], token)
        assert status == 422
        assert balance(account_key, token) == 1000

        # depois de colocar dinheiro, a mesma parcela ainda pode ser paga
        deposit(account_key, 100000, token)
        assert pay(loan["loan_key"], first["id"], token)[0] == 204

    def test_other_customer_cannot_pay(self):
        _, token, account_key = customer_with_account("low")
        _, loan = take_loan(account_key, token, 100000, 3)
        _, bob_token, _ = new_customer()

        status, _ = pay(loan["loan_key"], loan["installments"][0]["id"], bob_token)

        assert status == 403
        assert balance(account_key, token) == 100000

    def test_paying_every_installment_settles_the_debt(self):
        _, token, account_key = customer_with_account("low")
        deposit(account_key, 5000, token)                  # cobre os juros
        _, loan = take_loan(account_key, token, 100000, 3)

        for installment in loan["installments"]:
            assert pay(loan["loan_key"], installment["id"], token)[0] == 204

        assert balance(account_key, token) == 100000 + 5000 - loan["total_amount_due"]