from tests.utils import PayloadGenerator, RequestGenerator


class TestCustomerAccountCreation:
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

    def test_forbids_opening_account_for_other_customer(self):
        """Garante que o cliente não pode abrir conta no perfil de outra pessoa."""
        customer_key_1, access_token_1 = self._create_and_login_customer()
        customer_key_2, _ = self._create_and_login_customer()

        status, response = RequestGenerator.POST_customer_account(
            customer_key_2,
            {"type": "savings"},
            access_token_1
        )

        assert status == 403
        assert response["code"] == "QIT002003"  # ForbiddenAction

    def test_rejects_invalid_account_type(self):
        """Garante que tipos de conta fora do enum são barrados pelo schema."""
        customer_key, access_token = self._create_and_login_customer()

        status, response = RequestGenerator.POST_customer_account(
            customer_key,
            {"type": "investment"},
            access_token
        )

        assert status == 422
