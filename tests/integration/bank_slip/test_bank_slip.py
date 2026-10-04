import os
import requests 
from tests.utils.api_helpers import balance, deposit, new_customer, open_account, transfer, call, today_br
from datetime import date, timedelta
from tests.utils import RequestGenerator
import threading

MOCK_FAILS = 666
MOCK_TIMES_OUT = 777

#funcoes auxiliares
def _customer_with_account():
    customer_key, access_token, customer = new_customer()
    account_key = open_account(customer_key, access_token)

    return account_key, access_token

def issue(account_key: str, access_token: str, amount, expiration_date=None):
    payload = {"amount": amount}
    if expiration_date is not None:
        payload["expiration_date"] = expiration_date
    return call(
        "POST",
        f"/accounts/{account_key}/bank_slips",
        token=access_token,
        payload=payload,
    )

WEBHOOK_TOKEN = os.environ.get("BANKSLIP_WEBHOOK_TOKEN", "bankslip_webhook_token")


def pay(bank_slip_key, internal_token=True, webhook_token=WEBHOOK_TOKEN):
    """Simula o serviço de boletos avisando que o boleto foi pago.

    O provedor manda o segredo dele no BANKSLIP-WEBHOOK-TOKEN; um app
    cliente não tem esse segredo (passe webhook_token=None para simular).
    """
    headers = {"BANKSLIP-WEBHOOK-TOKEN": webhook_token} if webhook_token else {}
    return call("POST", f"/webhook/bank_slips/{bank_slip_key}/paid",
                internal_token=internal_token, headers=headers)

def test_mock_is_up():
    assert requests.get("http://localhost:8080/health_check", timeout=2).status_code == 204


class TestBankSlipEndpoints():
        
    def test_refuses_invalid_amount(self): 
        account_key, token = _customer_with_account() 
        for amount in [0, -10, "100", 10.5]: 
            status, body = issue(account_key, token, amount) 
            assert status == 400, amount

    def test_issue_creates_a_readable_bank_slip(self):    
        account_key, token = _customer_with_account()    

        status, body = issue(account_key, token, 5000)    
        assert status == 201, body    
        assert body["amount"] == 5000    
        assert body["account_key"] == account_key  

        status, read = call("GET", f"/bank_slips/{body['bank_slip_key']}", token)    
        assert status == 200    
        assert read["bank_slip_key"] == body["bank_slip_key"]    
        assert balance(account_key, token) == 0   # emitir não mexe no saldo    
        assert body["status"] == "issued"
        assert len(body["barcode"]) == 47
        assert body["transaction_key"] is None
        assert body["expiration_date"] == (today_br() + timedelta(days=3)).isoformat()

    def test_refuses_other_customers_account(self): 
        alice_account, _ = _customer_with_account()
        _, bob_token, _ = new_customer() 
        status, body = issue(alice_account, bob_token, 100) 
        assert status == 403 
        assert body["code"] == "QIT002003" 
        
    def test_refuses_blocked_account(self): 
        account_key, token = _customer_with_account() 
        RequestGenerator.PUT_account(account_key, {"status": "blocked"}, token) 
        assert issue(account_key, token, 100)[0] == 403 
    
    def test_requires_login(self): 
        account_key, _ = _customer_with_account() 
        assert issue(account_key, None, 100)[0] == 401

    def test_issue_with_custom_expiration(self): 
        account_key, token = _customer_with_account() 
        expiration = (today_br() + timedelta(days=10)).isoformat() 
        status, body = issue(account_key, token, 100, expiration) 
        assert status == 201 
        assert body["expiration_date"] == expiration 
        
    def test_refuses_expiration_in_the_past_or_too_far(self): 
        account_key, token = _customer_with_account() 
        for expiration in [(today_br() - timedelta(days=1)).isoformat(), (today_br() + timedelta(days=61)).isoformat(), "2026-02-30"]: 
            status, body = issue(account_key, token, 100, expiration) 
            assert status == 422, expiration 
            assert body["code"] == "QIT001025"

    def test_provider_error_returns_503_and_records_failure(self): 
        account_key, token = _customer_with_account() 
        status, body = issue(account_key, token, MOCK_FAILS) 
        assert status == 503 
        assert body["code"] == "QIT003001" 
    
    def test_provider_timeout_returns_503(self): 
        account_key, token = _customer_with_account() 
        status, body = issue(account_key, token, MOCK_TIMES_OUT) 
        assert status == 503 
        assert body["code"] == "QIT003001"

    def test_payment_credits_the_account(self):
        account_key, token = _customer_with_account()
        _, slip = issue(account_key, token, 2500)

        status, body = pay(slip["bank_slip_key"])

        assert status == 200, body
        assert body["status"] == "paid"
        assert body["transaction_key"] is not None
        assert balance(account_key, token) == 2500

        # o depósito aparece no extrato, pelo canal bank_slip
        _, statement = RequestGenerator.GET_account_statement(account_key, None, token)
        deposit = statement["data"][0]
        assert deposit["transaction_key"] == body["transaction_key"]
        assert deposit["type"] == "deposit"
        assert deposit["channel"] == "bank_slip"
        assert deposit["fee_amount"] == 0

    def test_webhook_requires_internal_token(self):
        account_key, token = _customer_with_account()
        _, slip = issue(account_key, token, 1000)

        status, body = pay(slip["bank_slip_key"], internal_token=False)

        assert status == 403
        assert body["code"] == "QIT000002"
        assert balance(account_key, token) == 0

    def test_paying_twice_credits_once(self):
        account_key, token = _customer_with_account()
        _, slip = issue(account_key, token, 1000)

        assert pay(slip["bank_slip_key"])[0] == 200      # 1º aviso: paga
        status, body = pay(slip["bank_slip_key"])        # 2º aviso: o mesmo boleto

        assert status == 409
        assert body["code"] == "QIT001026"
        assert balance(account_key, token) == 1000       # entrou UMA vez só

    def test_simultaneous_payment_notices_credit_once(self):
        """O serviço manda o mesmo aviso 10 vezes ao mesmo tempo: o dinheiro entra uma vez só."""
        account_key, token = _customer_with_account()
        _, slip = issue(account_key, token, 1000)

        results = []
        threads = [
            threading.Thread(target=lambda: results.append(pay(slip["bank_slip_key"])[0]))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(200) == 1
        assert results.count(409) == 9
        assert balance(account_key, token) == 1000

    def test_list_is_paginated_newest_first(self):
        account_key, token = _customer_with_account()
        for amount in (100, 200, 300):
            status, body = issue(account_key, token, amount)
            assert status == 201, body

        # página 0, com 2 itens: os dois MAIS NOVOS
        status, page0 = call("GET", f"/accounts/{account_key}/bank_slips", token,
                             params={"limit": "2", "page": "0"})
        assert status == 200, page0
        assert [b["amount"] for b in page0["data"]] == [300, 200]
        assert page0["is_last_page"] is False

        # página 1: só sobrou o mais antigo
        status, page1 = call("GET", f"/accounts/{account_key}/bank_slips", token,
                             params={"limit": "2", "page": "1"})
        assert status == 200, page1
        assert [b["amount"] for b in page1["data"]] == [100]
        assert page1["is_last_page"] is True

    def test_other_customer_cannot_list(self):
        account_key, _ = _customer_with_account()
        _, other_token, _ = new_customer()

        status, body = call("GET", f"/accounts/{account_key}/bank_slips", other_token)

        assert status == 403