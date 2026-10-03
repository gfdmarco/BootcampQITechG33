"""Entradas que derrubavam a API com 500 em vez de serem recusadas com 400.

- channel "bank_slip": não existe tarifa para ele (a tabela fee só tem
  pix/ted/card/international). Boleto só credita pelo webhook do provedor,
  nunca por POST /transactions.
- valores gigantes: estouram o BIGINT do Postgres. O teto é R$ 1 bilhão.
"""
from tests.utils.api_helpers import balance, call, deposit, new_customer, open_account

MAX_AMOUNT = 100_000_000_000          # R$ 1 bilhão em centavos


def two_accounts():
    k1, t1, _ = new_customer()
    a1 = open_account(k1, t1)
    deposit(a1, 10_000, t1)
    k2, t2, _ = new_customer()
    a2 = open_account(k2, t2)
    return t1, a1, t2, a2


class TestTransactionChannel:
    def test_transfer_with_bank_slip_channel_is_refused(self):
        t1, a1, t2, a2 = two_accounts()

        status, _ = call("POST", "/transactions", t1, payload={
            "type": "transfer", "origin_account_key": a1, "destination_account_key": a2,
            "amount": 100, "channel": "bank_slip",
        })

        assert status == 400
        assert balance(a1, t1) == 10_000
        assert balance(a2, t2) == 0

    def test_deposit_cannot_pretend_to_be_a_bank_slip(self):
        t1, a1, _, _ = two_accounts()

        status, _ = call("POST", "/transactions", t1, payload={
            "type": "deposit", "destination_account_key": a1, "amount": 100, "channel": "bank_slip",
        })

        assert status == 400
        assert balance(a1, t1) == 10_000


class TestTransactionMaxAmount:
    def test_amount_above_ceiling_is_400_not_500(self):
        t1, a1, _, _ = two_accounts()

        status, _ = call("POST", "/transactions", t1, payload={
            "type": "deposit", "destination_account_key": a1, "amount": 10 ** 19, "channel": "pix",
        })

        assert status == 400
        assert balance(a1, t1) == 10_000

    def test_amount_at_ceiling_is_accepted(self):
        t1, a1, _, _ = two_accounts()

        status, body = call("POST", "/transactions", t1, payload={
            "type": "deposit", "destination_account_key": a1, "amount": MAX_AMOUNT, "channel": "pix",
        })

        assert status == 201, body
        assert balance(a1, t1) == 10_000 + MAX_AMOUNT


class TestBankSlipWebhookMethod:
    def test_get_on_webhook_does_not_pay(self):
        """O webhook de pagamento só aceita POST; GET não pode ter efeito colateral."""
        status, _ = call("GET", "/webhook/bank_slips/00000000-0000-4000-8000-000000000000/paid", None)

        assert status == 405