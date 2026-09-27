from tests.utils import PayloadGenerator, RequestGenerator

class TestAccountStatement:
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

    def test_get_statement(self):
        """Extrato: Transação aparece nas duas contas; limit / page / is_last_page consistentes. Conta de outro -> 403; data invertida -> 400"""
        alice_key, alice_token = self._create_and_login_customer()
        alice_acc = self._create_account(alice_key, alice_token)
        
        bob_key, bob_token = self._create_and_login_customer()
        bob_acc = self._create_account(bob_key, bob_token)
        
        # Give Alice money
        RequestGenerator.POST_transaction({
            "account_key": alice_acc,
            "type": "deposit",
            "amount": 1000
        }, alice_token)
        
        # Transfer to Bob
        status, response = RequestGenerator.POST_transaction({
            "origin_account_key": alice_acc,
            "destination_account_key": bob_acc,
            "type": "pix",
            "amount": 100
        }, alice_token)
        
        transaction_key = response["transaction_key"]

        # Alice gets statement
        status, response = RequestGenerator.GET_account_statement(alice_acc, None, alice_token)
        assert status == 200
        assert "data" in response
        
        transaction_keys = [item["transaction_key"] for item in response["data"]]
        assert transaction_key in transaction_keys

        # Bob gets statement
        status, response = RequestGenerator.GET_account_statement(bob_acc, None, bob_token)
        assert status == 200
        
        transaction_keys = [item["transaction_key"] for item in response["data"]]
        assert transaction_key in transaction_keys

        # Bob tries to get Alice's statement -> 403
        status, response = RequestGenerator.GET_account_statement(alice_acc, None, bob_token)
        assert status == 403

        # Test date inversion -> 400
        status, response = RequestGenerator.GET_account_statement(
            alice_acc, 
            {"date_from": "2024-12-31", "date_to": "2024-01-01"}, 
            alice_token
        )
        assert status == 400
        assert response["code"] == "QIT000010"

        # Pagination validation: Alice fica com 4 transações no extrato
        status, _ = RequestGenerator.POST_transaction(PayloadGenerator.deposit(alice_acc, 10), alice_token)
        assert status == 201
        status, _ = RequestGenerator.POST_transaction(PayloadGenerator.deposit(alice_acc, 10), alice_token)
        assert status == 201

        # primeira página (page=0): 2 itens, ainda tem mais
        status, response = RequestGenerator.GET_account_statement(alice_acc, {"limit": 2, "page": 0}, alice_token)
        assert status == 200
        assert len(response["data"]) == 2
        assert response["is_last_page"] is False
        first_page_keys = [t["transaction_key"] for t in response["data"]]

        # segunda página (page=1): os 2 restantes, é a última
        status, response = RequestGenerator.GET_account_statement(alice_acc, {"limit": 2, "page": 1}, alice_token)
        assert status == 200
        assert len(response["data"]) == 2
        assert response["is_last_page"] is True
        second_page_keys = [t["transaction_key"] for t in response["data"]]

        # nenhuma transação aparece repetida nas duas páginas
        assert set(first_page_keys).isdisjoint(second_page_keys)
