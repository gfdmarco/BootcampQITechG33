from tests.utils import PayloadGenerator, RequestGenerator


class TestCustomerUpdate:
    def _create_and_login_customer(self, prefix="update_test"):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201
        
        customer_key = response["customer_key"]
        
        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        
        return customer_key, login_response["access_token"], payload

    def test_updates_customer_successfully(self):
        customer_key, access_token, _ = self._create_and_login_customer()

        patch_payload = {
            "name": "Novo Nome Atualizado",
            "email": "novo.email.atualizado@exemplo.com.br"
        }

        status, response = RequestGenerator.PATCH_customer(customer_key, patch_payload, access_token)

        assert status == 200
        assert response["name"] == "Novo Nome Atualizado"
        assert response["email"] == "novo.email.atualizado@exemplo.com.br"

    def test_forbids_updating_other_customer(self):
        # Cria dois clientes
        customer_key_1, access_token_1, _ = self._create_and_login_customer("c1")
        customer_key_2, access_token_2, _ = self._create_and_login_customer("c2")

        patch_payload = {"name": "Hacker tentando mudar o nome"}

        # Cliente 1 tenta atualizar o Cliente 2
        status, response = RequestGenerator.PATCH_customer(customer_key_2, patch_payload, access_token_1)

        assert status == 403
        assert response["code"] == "QIT002003"  # ForbiddenAction

    def test_refuses_duplicated_email_on_update(self):
        customer_key_1, _, original_payload_1 = self._create_and_login_customer("c1")
        customer_key_2, access_token_2, _ = self._create_and_login_customer("c2")

        # Cliente 2 tenta colocar o email do Cliente 1
        patch_payload = {"email": original_payload_1["email"]}

        status, response = RequestGenerator.PATCH_customer(customer_key_2, patch_payload, access_token_2)

        assert status == 409
        assert response["code"] == "QIT001005"  # DuplicatedEmail
