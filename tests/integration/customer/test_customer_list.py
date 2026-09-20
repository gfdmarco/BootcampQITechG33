from tests.utils import PayloadGenerator, RequestGenerator


class TestCustomerList:
    def _create_and_login_customer(self, name_suffix=""):
        payload = PayloadGenerator.create_customer_payload()
        if name_suffix:
            payload["name"] = f"{payload['name']} {name_suffix}"
            
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201
        
        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        
        return login_response["access_token"], payload

    def test_list_customers_with_pagination(self):
        # 1. Cria dois clientes para garantir que existem
        access_token, payload1 = self._create_and_login_customer("PaginadoUm")
        _, payload2 = self._create_and_login_customer("PaginadoDois")

        # 2. Busca a lista limitando a 1 (para forçar paginação)
        params = {"limit": "1", "page": "0"}
        status, response = RequestGenerator.GET_customers_list(params, access_token)

        assert status == 200
        assert "data" in response
        assert len(response["data"]) == 1
        assert response["limit"] == 1
        assert response["page"] == 0
        assert response["is_last_page"] is False

    def test_list_customers_with_filters(self):
        access_token, payload = self._create_and_login_customer("UnicoSilva")

        # Filtra pelo CPF exato do cliente que criamos
        params = {"document_number": payload["document_number"]}
        status, response = RequestGenerator.GET_customers_list(params, access_token)

        assert status == 200
        assert len(response["data"]) == 1
        assert response["data"][0]["document_number"] == payload["document_number"]

        # Filtra por um nome que não existe
        params_not_found = {"name": "NomeQueNaoExisteNesteBancoX123"}
        status_empty, response_empty = RequestGenerator.GET_customers_list(params_not_found, access_token)
        
        assert status_empty == 200
        assert len(response_empty["data"]) == 0
        assert response_empty["is_last_page"] is True
