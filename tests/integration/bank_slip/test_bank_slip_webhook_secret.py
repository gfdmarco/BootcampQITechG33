"""Só o provedor de boletos consegue marcar um boleto como pago.

Antes, o webhook exigia só o INTERNAL-TOKEN — o mesmo que todo app cliente
manda. Bastava o cliente chamar POST /webhook/bank_slips/{key}/paid para
receber o crédito sem pagar nada. Agora o webhook também exige o
BANKSLIP-WEBHOOK-TOKEN, segredo que só o provedor tem.
"""
import os

from tests.utils.api_helpers import balance, call, new_customer, open_account

WEBHOOK_TOKEN = os.environ.get("BANKSLIP_WEBHOOK_TOKEN", "bankslip_webhook_token")


def issued_slip(amount=5000):
    key, token, _ = new_customer()
    account = open_account(key, token)
    status, slip = call("POST", f"/accounts/{account}/bank_slips", token, payload={"amount": amount})
    assert status == 201, slip
    return token, account, slip


def webhook(slip_key, token=None, secret=None):
    headers = {"BANKSLIP-WEBHOOK-TOKEN": secret} if secret is not None else {}
    return call("POST", f"/webhook/bank_slips/{slip_key}/paid", token, headers=headers)


class TestWebhookSecret:
    def test_client_with_only_internal_token_cannot_pay_own_slip(self):
        token, account, slip = issued_slip()

        status, body = webhook(slip["bank_slip_key"], token=token)   # INTERNAL-TOKEN + JWT, sem o segredo

        assert status == 403
        assert body["code"] == "QIT002003"
        assert balance(account, token) == 0
        _, read = call("GET", f"/bank_slips/{slip['bank_slip_key']}", token)
        assert read["status"] == "issued"

    def test_wrong_secret_is_refused(self):
        token, account, slip = issued_slip()

        status, _ = webhook(slip["bank_slip_key"], secret="chute")

        assert status == 403
        assert balance(account, token) == 0

    def test_provider_with_the_secret_pays(self):
        token, account, slip = issued_slip(5000)

        status, body = webhook(slip["bank_slip_key"], secret=WEBHOOK_TOKEN)

        assert status == 200, body
        assert body["status"] == "paid"
        assert balance(account, token) == 5000
