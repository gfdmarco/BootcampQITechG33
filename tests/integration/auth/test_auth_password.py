from tests.utils import PayloadGenerator, RequestGenerator


class TestAuthPassword:
    def _create_and_login_customer(self):
        payload = PayloadGenerator.create_customer_payload(password="SenhaAntiga123")
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201
        
        login_payload = {
            "document_number": payload["document_number"],
            "password": "SenhaAntiga123"
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        
        return login_response["access_token"], payload["document_number"]

    def test_updates_password_successfully(self):
        access_token, doc_number = self._create_and_login_customer()

        update_payload = {
            "current_password": "SenhaAntiga123",
            "new_password": "SenhaNovaSegura123!"
        }

        # Muda a senha
        status, response = RequestGenerator.PUT_auth_password(update_payload, access_token)
        assert status == 200
        assert response["message"] == "Password successfully updated."

        # Tenta logar com a senha velha (deve falhar)
        status_old, _ = RequestGenerator.POST_auth_login({
            "document_number": doc_number,
            "password": "SenhaAntiga123"
        })
        assert status_old == 401

        # Tenta logar com a senha nova (deve passar)
        status_new, _ = RequestGenerator.POST_auth_login({
            "document_number": doc_number,
            "password": "SenhaNovaSegura123!"
        })
        assert status_new == 200

    def test_refuses_wrong_current_password(self):
        access_token, doc_number = self._create_and_login_customer()

        update_payload = {
            "current_password": "SenhaErrada!",
            "new_password": "SenhaNovaSegura123!"
        }

        status, response = RequestGenerator.PUT_auth_password(update_payload, access_token)
        assert status == 401
        assert response["code"] == "QIT002001"  # InvalidCredentials

        # Garante que a senha antiga continua funcionando
        status_old, _ = RequestGenerator.POST_auth_login({
            "document_number": doc_number,
            "password": "SenhaAntiga123"
        })
        assert status_old == 200
