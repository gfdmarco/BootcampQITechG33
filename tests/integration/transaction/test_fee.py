from tests.utils import PayloadGenerator, RequestGenerator

class TestTransactionFees:
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

    def test_fees(self):
        """Tarifa: PIX 0, TED/cartão 5%, internacional 8%, com a regra de arredondamento documentada"""
        alice_key, alice_token = self._create_and_login_customer()
        alice_acc = self._create_account(alice_key, alice_token)
        
        bob_key, bob_token = self._create_and_login_customer()
        bob_acc = self._create_account(bob_key, bob_token)

        RequestGenerator.POST_transaction({
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 10000
        }, alice_token)
        
        # Initial balance 10000

        # TED/cartão 5%
        # 199 * 5% = 9.95, rounded down = 9 centavos. 
        # Wait, amount is in float (e.g. 1.99)? The audit says "Cálculo certo (TED 5% sobre 199 = 9 centavos)". So amount is probably in integer cents or float. Assuming integer cents as in "199" = R$ 1.99.
        # Let's transfer 199.
        payload = {
            "origin_account_key": alice_acc,
            "destination_account_key": bob_acc,
            "type": "ted",
            "amount": 199
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 201
        
        # Fee should be 9
        _, alice_info = RequestGenerator.GET_account(alice_acc, alice_token)
        # 10000 - 199 (transfer) - 9 (fee) = 9792
        assert alice_info["balance"] == 9792

        # Internacional 8%
        # Transfer 100 -> 8% of 100 = 8.
        payload = {
            "origin_account_key": alice_acc,
            "destination_account_key": bob_acc,
            "type": "international",
            "amount": 100
        }
        status, response = RequestGenerator.POST_transaction(payload, alice_token)
        assert status == 201
        
        _, alice_info = RequestGenerator.GET_account(alice_acc, alice_token)
        # 9792 - 100 - 8 = 9684
        assert alice_info["balance"] == 9684
