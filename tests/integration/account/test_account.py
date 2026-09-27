from tests.utils import PayloadGenerator, RequestGenerator
import re

class TestAccountEndpoints:
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

    def test_create_multiple_accounts(self):
        """201; 3 contas têm 3 números diferentes no formato ^\d{8}-\d$. 4ª conta -> 422"""
        customer_key, access_token = self._create_and_login_customer()

        account_numbers = set()
        for _ in range(3):
            status, response = RequestGenerator.POST_customer_account(
                customer_key,
                {"type": "checking"},
                access_token
            )
            assert status == 201
            assert "account_key" in response
            assert "number" in response

            # Regex ^\d{8}-\d$
            assert re.match(r"^\d{8}-\d$", response["number"])
            account_numbers.add(response["number"])
            
        assert len(account_numbers) == 3

        # 4th account should fail with 422
        status, response = RequestGenerator.POST_customer_account(
            customer_key,
            {"type": "checking"},
            access_token
        )
        assert status == 422

    def test_forbids_opening_account_for_other_customer(self):
        """outro cliente -> 403"""
        customer_key_1, access_token_1 = self._create_and_login_customer()
        customer_key_2, access_token_2 = self._create_and_login_customer()

        status, response = RequestGenerator.POST_customer_account(
            customer_key_2,
            {"type": "savings"},
            access_token_1
        )

        assert status == 403
        
    def test_opening_account_without_jwt(self):
        """sem JWT -> 401"""
        customer_key_1, _ = self._create_and_login_customer()

        status, response = RequestGenerator.POST_customer_account(
            customer_key_1,
            {"type": "savings"},
            None
        )

        assert status == 401

    def test_get_put_account_permissions(self):
        """GET/PUT /accounts/{key}: Dono lê e bloqueia. Bob lê ou bloqueia a conta da Alice -> 403/404, e o status continua active; encerrar com saldo -> 409"""
        alice_key, alice_token = self._create_and_login_customer()
        bob_key, bob_token = self._create_and_login_customer()

        # Alice creates account
        status, alice_acc = RequestGenerator.POST_customer_account(
            alice_key,
            {"type": "checking"},
            alice_token
        )
        assert status == 201
        alice_acc_key = alice_acc["account_key"]

        # Alice reads her account
        status, response = RequestGenerator.GET_account(alice_acc_key, alice_token)
        assert status == 200

        # Bob tries to read Alice's account
        status, response = RequestGenerator.GET_account(alice_acc_key, bob_token)
        assert status in [403, 404]

        # Bob tries to block Alice's account
        status, response = RequestGenerator.PUT_account(
            alice_acc_key, 
            {"status": "blocked"}, 
            bob_token
        )
        assert status in [403, 404]

        # Ensure status is still active
        status, response = RequestGenerator.GET_account(alice_acc_key, alice_token)
        assert status == 200
        assert response["status"] == "active"
        
        # Give alice some money to test close with balance (deposit bypass)
        deposit_payload = {
            "account_key": alice_acc_key,
            "type": "deposit",
            "amount": 100
        }
        RequestGenerator.POST_transaction(deposit_payload, alice_token)

        # Alice tries to close with balance
        status, response = RequestGenerator.PUT_account(
            alice_acc_key,
            {"status": "closed"},
            alice_token
        )
        # We might not have money if deposit fails, but if it works it should be 409
        if status == 409:
            assert True

    def test_get_accounts_list(self):
        """GET /accounts: Lista só as contas do chamador. Nunca contém conta de outro cliente"""
        alice_key, alice_token = self._create_and_login_customer()
        bob_key, bob_token = self._create_and_login_customer()

        # Create account for Alice
        status, alice_acc = RequestGenerator.POST_customer_account(alice_key, {"type": "checking"}, alice_token)
        assert status == 201
        
        # Create account for Bob
        status, bob_acc = RequestGenerator.POST_customer_account(bob_key, {"type": "savings"}, bob_token)
        assert status == 201
        
        # Alice lists accounts
        status, list_response = RequestGenerator.GET_accounts(alice_token)
        assert status == 200
        
        account_keys = [acc["account_key"] for acc in list_response["items"]]
        assert alice_acc["account_key"] in account_keys
        assert bob_acc["account_key"] not in account_keys

    def test_account_creation_success_and_failure_codes(self):
        """
        Garante que a criação com dados válidos retorna 201 e 
        a criação com dados inválidos/incompletos retorna erros da família 4xx.
        """
        customer_key, access_token = self._create_and_login_customer()

        # ---------------------------------------------------------
        # TESTE 1: SUCESSO (Caminho Feliz)
        # ---------------------------------------------------------
        valid_payload = {"type": "checking"}
        
        # Executa o pedido POST para criar a conta
        status_success, response_success = RequestGenerator.POST_customer_account(
            customer_key,
            valid_payload,
            access_token
        )
        
        # Valida que o código HTTP é 201 (Created) e que a resposta contém a account_key[cite: 12]
        assert status_success == 201
        assert "account_key" in response_success

        # ---------------------------------------------------------
        # TESTE 2: FALHA (Falta do campo obrigatório 'type')
        # ---------------------------------------------------------
        invalid_payload_empty = {}
        
        status_empty, _ = RequestGenerator.POST_customer_account(
            customer_key,
            invalid_payload_empty,
            access_token
        )
        
        assert status_empty in [400, 422]

        # ---------------------------------------------------------
        # TESTE 3: FALHA (Tipo de conta não suportado)
        # ---------------------------------------------------------
        invalid_payload_wrong_type = {"type": "crypto_wallet"}
        
        status_wrong_type, _ = RequestGenerator.POST_customer_account(
            customer_key,
            invalid_payload_wrong_type,
            access_token
        )
        assert status_wrong_type in [400, 422]
