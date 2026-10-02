from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import ClientRequisition
from tests.utils.random_generator import RandomGenerator

class TestCorporateCreate:
    def _create_and_login_customer(self):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201

        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        return response["customer_key"], login_response["access_token"]

    def _generate_clean_cnpj(self):
        return RandomGenerator.generate_cnpj().replace(".", "").replace("/", "").replace("-", "")

    def POST_corporate(self, payload: dict, access_token: str):
        headers = {
            "INTERNAL-TOKEN": "default_token",
            "Authorization": f"Bearer {access_token}"
        }
        response = ClientRequisition.send("POST", "/corporates", payload=payload, headers=headers)
        return response.response_status, response.response_json

    def test_create_with_valid_cnpj(self):
        """Creates a corporate entity with a valid CNPJ"""
        customer_key, token = self._create_and_login_customer()
        
        valid_cnpj = self._generate_clean_cnpj()
        payload = {
            "cnpj": valid_cnpj,
            "company_name": "Acme Corp",
            "trade_name": "Acme"
        }
        
        status, response = self.POST_corporate(payload, token)
        assert status == 201
        assert "corporate_key" in response
        assert response["cnpj"] == valid_cnpj
        assert response["status"] == "created" 

    def test_invalid_cnpj_refused(self):
        """Invalid checksum CNPJ should be refused"""
        customer_key, token = self._create_and_login_customer()
        
        payload = {
            "cnpj": "11111111111111", 
            "company_name": "Acme Corp",
        }
        status, response = self.POST_corporate(payload, token)
        assert status == 422

    def test_duplicate_cnpj_refused(self):
        """Second registration with same CNPJ returns 409 Conflict"""
        customer_key, token = self._create_and_login_customer()
        
        dup_cnpj = self._generate_clean_cnpj()
        payload = {
            "cnpj": dup_cnpj, 
            "company_name": "Acme Corp"
        }
        
        # First
        status, _ = self.POST_corporate(payload, token)
        assert status == 201
        
        # Second
        status, response = self.POST_corporate(payload, token)
        assert status == 409

    def test_creator_becomes_owner(self):
        """The user who created the corporate entity becomes its 'owner' member."""
        customer_key, token = self._create_and_login_customer()
        
        owner_cnpj = self._generate_clean_cnpj()
        payload = {
            "cnpj": owner_cnpj, 
            "company_name": "Acme Corp"
        }
        status, response = self.POST_corporate(payload, token)
        assert status == 201
        
        # Fetch details to verify membership
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {token}"}
        resp = ClientRequisition.send("GET", f"/corporates/{response['corporate_key']}", headers=headers)
        
        assert resp.response_status == 200
        assert "members" in resp.response_json
        members = resp.response_json["members"]
        assert len(members) == 1
        assert members[0]["customer_key"] == customer_key
        assert members[0]["role"] == "owner"
