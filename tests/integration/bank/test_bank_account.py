"""Conta interna do banco (tesouraria): para onde vão tarifas e parcelas.

Antes, a tarifa saía da conta do cliente e não entrava em lugar nenhum, e
a parcela paga sumia do saldo sem aparecer no extrato. A regra agora é
de conservação: todo centavo que sai de um cliente entra em alguma conta.

O saldo da tesouraria é lido direto no banco de dados: nenhum cliente
tem acesso a ela pela API (é esse o ponto).
"""
import threading

from sqlalchemy import create_engine, text

from tests.utils import RequestGenerator
from tests.utils.api_helpers import balance, call, deposit, new_customer, open_account, set_risk_score, transfer
from tests.utils.db_utils import DbUtils

BANK_ACCOUNT_KEY = "00000000-0000-4000-8000-000000000002"
_engine = create_engine(DbUtils.database_url())


def bank_balance() -> int:
    with _engine.connect() as conn:
        return conn.execute(
            text("SELECT balance FROM account WHERE account_key = :k"), {"k": BANK_ACCOUNT_KEY}
        ).scalar_one()


def funded_pair(amount=100_000):
    k1, t1, _ = new_customer()
    a1 = open_account(k1, t1)
    deposit(a1, amount, t1)
    k2, t2, _ = new_customer()
    a2 = open_account(k2, t2)
    return (k1, t1, a1), (k2, t2, a2)


class TestFeesGoToTheBank:
    def test_ted_fee_is_credited_to_the_bank(self):
        (_, t1, a1), (_, t2, a2) = funded_pair()
        before = bank_balance()

        status, body = transfer(a1, a2, 10_000, t1, channel="ted")

        assert status == 201, body
        assert balance(a1, t1) == 100_000 - 10_000 - 500     # TED: 5%
        assert balance(a2, t2) == 10_000
        assert bank_balance() - before == 500

    def test_international_fee_is_8_percent(self):
        (k1, t1, a1), (_, _, a2) = funded_pair()
        set_risk_score(k1, "low")                              # libera o canal international
        before = bank_balance()

        status, body = transfer(a1, a2, 10_000, t1, channel="international")

        assert status == 201, body
        assert bank_balance() - before == 800

    def test_pix_has_no_fee_and_bank_gets_nothing(self):
        (_, t1, a1), (_, _, a2) = funded_pair()
        before = bank_balance()

        transfer(a1, a2, 10_000, t1, channel="pix")

        assert bank_balance() == before

    def test_failed_transfer_does_not_pay_the_bank(self):
        (_, t1, a1), (_, _, a2) = funded_pair(amount=1_000)
        before = bank_balance()

        status, _ = transfer(a1, a2, 1_000, t1, channel="ted")  # 1.000 + 50 de tarifa > saldo

        assert status == 422
        assert balance(a1, t1) == 1_000
        assert bank_balance() == before

    def test_risk_denied_transfer_does_not_pay_the_bank(self):
        """O crédito da tarifa está na mesma transação: se o Motor de Risco nega, tudo volta."""
        (k1, t1, a1), (_, _, a2) = funded_pair()
        set_risk_score(k1, "high")                             # high: international bloqueado
        before = bank_balance()

        status, _ = transfer(a1, a2, 10_000, t1, channel="international")

        assert status == 403
        assert balance(a1, t1) == 100_000
        assert bank_balance() == before

    def test_money_is_conserved_under_concurrency(self):
        """10 TEDs simultâneas: nenhum deadlock, e o banco recebe exatamente a soma das tarifas."""
        pairs = [funded_pair() for _ in range(10)]
        before = bank_balance()
        results = []

        def send(pair):
            (_, t1, a1), (_, _, a2) = pair
            results.append(transfer(a1, a2, 10_000, t1, channel="ted")[0])

        threads = [threading.Thread(target=send, args=(p,)) for p in pairs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(201) == 10, results
        assert bank_balance() - before == 10 * 500


class TestInstallmentsGoToTheBank:
    def _loan(self):
        key, token, _ = new_customer()
        account = open_account(key, token)
        set_risk_score(key, "low")
        status, loan = call("POST", "/loans", token, payload={
            "account_key": account, "requested_amount": 100_000, "installments_count": 2,
        })
        assert status == 201, loan
        return token, account, loan

    def test_paid_installment_is_credited_to_the_bank(self):
        token, account, loan = self._loan()
        first = loan["installments"][0]
        before = bank_balance()

        status, _ = call("POST", f"/loans/{loan['loan_key']}/installments/{first['id']}/pay", token)

        assert status == 204
        assert balance(account, token) == 100_000 - first["amount"]
        assert bank_balance() - before == first["amount"]

    def test_paid_installment_shows_in_the_statement(self):
        token, account, loan = self._loan()
        first = loan["installments"][0]

        call("POST", f"/loans/{loan['loan_key']}/installments/{first['id']}/pay", token)

        _, statement = RequestGenerator.GET_account_statement(account, None, token)
        lines = [(t["amount"], t["channel"]) for t in statement["data"]]
        assert (first["amount"], "loan") in lines             # o pagamento
        assert (100_000, "loan") in lines                     # o crédito do empréstimo

    def test_unpaid_installment_moves_nothing(self):
        token, account, loan = self._loan()
        # esvazia a conta
        k, t, _ = new_customer()
        dest = open_account(k, t)
        transfer(account, dest, 100_000, token)
        before = bank_balance()

        status, _ = call("POST", f"/loans/{loan['loan_key']}/installments/{loan['installments'][0]['id']}/pay", token)

        assert status == 422
        assert bank_balance() == before


class TestBankAccountIsClosedToCustomers:
    def test_customer_cannot_transfer_to_the_bank_account(self):
        (_, t1, a1), _ = funded_pair()
        before = bank_balance()

        status, _ = transfer(a1, BANK_ACCOUNT_KEY, 1_000, t1)

        assert status == 403
        assert balance(a1, t1) == 100_000
        assert bank_balance() == before

    def test_customer_cannot_read_the_bank_account(self):
        _, token, _ = new_customer()

        assert RequestGenerator.GET_account(BANK_ACCOUNT_KEY, token)[0] == 403

    def test_nobody_logs_in_as_the_bank(self):
        status, _ = RequestGenerator.POST_auth_login({"document_number": "000.000.000-00", "password": "Senha1234"})

        assert status == 401