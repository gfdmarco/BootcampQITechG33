import time

from tests.utils import PayloadGenerator, RequestGenerator


class TestAuthAndSecurity:
    def _create_test_customer(self):
        """Helper para criar um cliente e devolver o payload usado + a chave."""
        payload = PayloadGenerator.create_customer_payload(password="SenhaForte123")
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201
        return payload, response["customer_key"]

    def test_login_success_and_routing_security(self):
        # 1. Cria o cliente
        payload, customer_key = self._create_test_customer()

        # 2. Faz login
        login_payload = {
            "document_number": payload["document_number"],
            "password": "SenhaForte123"
        }
        status, response = RequestGenerator.POST_auth_login(login_payload)
        
        assert status == 200
        assert "access_token" in response
        assert "refresh_token" in response
        
        access_token = response["access_token"]

        # 3. Tenta acessar rota fechada SEM token (deve falhar)
        status_unauth, response_unauth = RequestGenerator.GET_customer(customer_key)
        assert status_unauth == 401
        assert response_unauth["code"] == "QIT002002"

        # 4. Tenta acessar rota fechada COM token falso (deve falhar)
        status_fake, response_fake = RequestGenerator.GET_customer(customer_key, access_token="token_falso")
        assert status_fake == 401
        assert response_fake["code"] == "QIT002002"

        # 5. Tenta acessar rota fechada COM o token verdadeiro (deve passar)
        status_ok, response_ok = RequestGenerator.GET_customer(customer_key, access_token=access_token)
        assert status_ok == 200
        assert response_ok["document_number"] == payload["document_number"]

    def test_login_invalid_password_returns_401(self):
        payload, _ = self._create_test_customer()

        login_payload = {
            "document_number": payload["document_number"],
            "password": "SenhaErrada123"
        }
        status, response = RequestGenerator.POST_auth_login(login_payload)
        
        assert status == 401
        assert response["code"] == "QIT002001"

    def test_login_invalid_cpf_returns_401(self):
        # Mesmo erro QIT002001 para não vazar se o CPF existe ou não
        login_payload = {
            "document_number": "111.111.111-11",
            "password": "SenhaQualquer123"
        }
        status, response = RequestGenerator.POST_auth_login(login_payload)
        
        assert status == 401
        assert response["code"] == "QIT002001"

    def test_refresh_token_issues_new_access_token(self):
        payload, _ = self._create_test_customer()

        login_payload = {
            "document_number": payload["document_number"],
            "password": "SenhaForte123"
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        
        refresh_token = login_response["refresh_token"]
        old_access_token = login_response["access_token"]

        # Espera 1 segundo para garantir que o timestamp de emissão (iat/exp) será diferente
        # (se for muito rápido, o token gerado pode ser idêntico)
        time.sleep(1)

        refresh_payload = {"refresh_token": refresh_token}
        status, refresh_response = RequestGenerator.POST_auth_refresh(refresh_payload)

        assert status == 200
        assert "access_token" in refresh_response
        assert refresh_response["access_token"] != old_access_token

    def test_refresh_token_refuses_access_token(self):
        """Garante que ninguém use um Access Token na rota de Refresh."""
        payload, _ = self._create_test_customer()

        login_payload = {
            "document_number": payload["document_number"],
            "password": "SenhaForte123"
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        
        # Manda o access_token onde deveria ser o refresh_token
        access_token = login_response["access_token"]

        refresh_payload = {"refresh_token": access_token}
        status, response = RequestGenerator.POST_auth_refresh(refresh_payload)

        assert status == 401
        assert response["code"] == "QIT002002"
