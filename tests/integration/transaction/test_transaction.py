from tests.utils import PayloadGenerator, RequestGenerator
import threading
import time

class TestTransactionEndpoints:
    def _create_and_login_customer(self):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201

        customer_key = response["customer_key"]

        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)

        return customer_key, login_response["access_token"]
        
    def _create_account(self, customer_key, access_token):
        status, response = RequestGenerator.POST_customer_account(
            customer_key,
            {"type": "checking"},
            access_token
        )
        assert status == 201
        return response["account_key"]

    def test_deposit(self):
        """POST /transactions depósito. Saldo sobe exatamente o valor. Conta de outro, conta bloqueada, amount 0, -5, "100", 100.5 -> recusar"""
        alice_key, alice_token = self._create_and_login_customer()
        alice_acc = self._create_account(alice_key, alice_token)
        
        bob_key, bob_token = self._create_and_login_customer()
        bob_acc = self._create_account(bob_key, bob_token)

        # Alice deposits 100
        payload = {
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 100
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 201
        
        # Check balance
        status, acc_info = RequestGenerator.GET_account(alice_acc, alice_token)
        assert acc_info["balance"] == 100

        # Try to deposit to another person's account (Alice deposits to Bob) -> Should reject? The document says "Conta de outro" should be rejected.
        payload = {
            "account_key": bob_acc,
            "type": "deposit",
            "amount": 100
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 403

        # Invalid amounts
        for invalid_amount in [0, -5, "100", 100.5]:
            payload = {
                "account_key": alice_acc,
                "type": "deposit",
                "amount": invalid_amount
            }
            status, response = RequestGenerator.POST_transaction(payload, alice_token)
            assert status == 422
            
        # Block account and try to deposit
        RequestGenerator.PUT_account(alice_acc, {"status": "blocked"}, alice_token)
        payload = {
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 100
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 422 # Or 403, but it should be rejected

    def test_transfer(self):
        """POST /transactions transferência. Origem = antes - valor - tarifa; destino = antes + valor."""
        alice_key, alice_token = self._create_and_login_customer()
        alice_acc = self._create_account(alice_key, alice_token)
        
        bob_key, bob_token = self._create_and_login_customer()
        bob_acc = self._create_account(bob_key, bob_token)

        # Deposit to Alice
        RequestGenerator.POST_transaction({
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 1000
        }, alice_token)
        
        # Transfer Alice -> Bob
        payload = {
            "origin_account_key": alice_acc,
            "destination_account_key": bob_acc,
            "type": "pix",
            "amount": 100
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 201
        
        # Check balances
        status, alice_info = RequestGenerator.GET_account(alice_acc, alice_token)
        # PIX tariff is 0
        assert alice_info["balance"] == 900
        
        status, bob_info = RequestGenerator.GET_account(bob_acc, bob_token)
        assert bob_info["balance"] == 100

        # Transfer without balance -> 422
        payload = {
            "origin_account_key": alice_acc,
            "destination_account_key": bob_acc,
            "type": "pix",
            "amount": 901
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 422
        
        # Check balances remain intact
        status, alice_info = RequestGenerator.GET_account(alice_acc, alice_token)
        assert alice_info["balance"] == 900

        # Try to transfer from Bob using Alice's token -> 403
        payload = {
            "origin_account_key": bob_acc,
            "destination_account_key": alice_acc,
            "type": "pix",
            "amount": 50
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 403
        
        # Try same account transfer -> reject
        payload = {
            "origin_account_key": alice_acc,
            "destination_account_key": alice_acc,
            "type": "pix",
            "amount": 50
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status in [422, 400] # should be rejected

    def test_concurrency(self):
        """Concorrência: 20 transferências simultâneas de 100 com saldo 1.000: no máximo 10 aceitas, e aceitas * 100 + saldo final = 1.000"""
        alice_key, alice_token = self._create_and_login_customer()
        alice_acc = self._create_account(alice_key, alice_token)
        
        bob_key, bob_token = self._create_and_login_customer()
        bob_acc = self._create_account(bob_key, bob_token)

        # Deposit 1000 to Alice
        status, _ = RequestGenerator.POST_transaction({
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 1000
        }, alice_token)
        assert status == 201

        results = []
        def transfer():
            payload = {
                "origin_account_key": alice_acc,
                "destination_account_key": bob_acc,
                "type": "pix", # pix so no fees interfere with simple math
                "amount": 100
            }
            status, response = RequestGenerator.POST_transaction(payload, alice_token)
            results.append(status)

        threads = []
        for _ in range(20):
            t = threading.Thread(target=transfer)
            threads.append(t)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        accepted = results.count(201)
        assert accepted <= 10
        
        _, alice_info = RequestGenerator.GET_account(alice_acc, alice_token)
        final_balance = alice_info["balance"]
        assert accepted * 100 + final_balance == 1000

