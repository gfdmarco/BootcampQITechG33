from tests.utils import PayloadGenerator, RequestGenerator


class TestCustomerDelete:
    def _create_and_login_customer(self, prefix="del_test"):
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

    def test_deletes_customer_successfully_and_anonymizes_data(self):
        customer_key, access_token, original_payload = self._create_and_login_customer()

        # 1. Encerra a conta
        status, response = RequestGenerator.DELETE_customer(customer_key, access_token)
        assert status == 204
        assert response is None

        # 2. Busca o cliente para ver se o status mudou e os dados foram anonimizados
        status_get, response_get = RequestGenerator.GET_customer(customer_key, access_token)
        assert status_get == 200
        
        assert response_get["status"]["enumerator"] == "failed"
        assert response_get["name"] == "DELETED_USER"
        assert "deleted_" in response_get["email"]

        # O CPF deve continuar lá (por questões de compliance)
        assert response_get["document_number"] == original_payload["document_number"]

        # 3. Garante que o login com a senha antiga não funciona mais
        status_login, _ = RequestGenerator.POST_auth_login({
            "document_number": original_payload["document_number"],
            "password": original_payload["password"]
        })
        assert status_login == 401

    def test_forbids_deleting_other_customer(self):
        customer_key_1, access_token_1, _ = self._create_and_login_customer("c1")
        customer_key_2, access_token_2, _ = self._create_and_login_customer("c2")

        # Cliente 1 tenta deletar o Cliente 2
        status, response = RequestGenerator.DELETE_customer(customer_key_2, access_token_1)

        assert status == 403
        assert response["code"] == "QIT002003"  # ForbiddenAction
