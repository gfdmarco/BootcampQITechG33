from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import ClientRequisition
from tests.utils.random_generator import RandomGenerator

class TestCorporateMembers:
    def _create_and_login_customer(self):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        return response["customer_key"], login_response["access_token"]

    def _create_corporate(self, token):
        cnpj = RandomGenerator.generate_cnpj().replace(".", "").replace("/", "").replace("-", "")
        payload = {"cnpj": cnpj, "company_name": "Test Corp"}
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {token}"}
        resp = ClientRequisition.send("POST", "/corporates", payload=payload, headers=headers)
        return resp.response_json["corporate_key"]

    def test_owner_adds_member(self):
        """Owner can add a new member"""
        owner_key, owner_token = self._create_and_login_customer()
        new_member_key, _ = self._create_and_login_customer()
        
        corp_key = self._create_corporate(owner_token)
        
        payload = {
            "customer_key": new_member_key,
            "role": "operator"
        }
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {owner_token}"}
        resp = ClientRequisition.send("POST", f"/corporates/{corp_key}/members", payload=payload, headers=headers)
        
        assert resp.response_status == 201

    def test_non_owner_cannot_add_member(self):
        """A user without the 'owner' role cannot add members"""
        owner_key, owner_token = self._create_and_login_customer()
        finance_member_key, finance_token = self._create_and_login_customer()
        other_member_key, _ = self._create_and_login_customer()
        
        corp_key = self._create_corporate(owner_token)
        
        # Add a finance member first
        payload = {"customer_key": finance_member_key, "role": "finance"}
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {owner_token}"}
        ClientRequisition.send("POST", f"/corporates/{corp_key}/members", payload=payload, headers=headers)
        
        # Now finance member tries to add someone
        payload = {"customer_key": other_member_key, "role": "viewer"}
        headers_finance = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {finance_token}"}
        resp = ClientRequisition.send("POST", f"/corporates/{corp_key}/members", payload=payload, headers=headers_finance)
        
        assert resp.response_status == 403

    def test_removed_member_loses_access(self):
        """A removed member cannot view corporate details"""
        owner_key, owner_token = self._create_and_login_customer()
        member_key, member_token = self._create_and_login_customer()
        corp_key = self._create_corporate(owner_token)
        
        # Add member
        headers_owner = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {owner_token}"}
        ClientRequisition.send("POST", f"/corporates/{corp_key}/members", payload={"customer_key": member_key, "role": "viewer"}, headers=headers_owner)
        
        # View (should work)
        headers_member = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {member_token}"}
        resp = ClientRequisition.send("GET", f"/corporates/{corp_key}", headers=headers_member)
        assert resp.response_status == 200
        
        # Remove member
        ClientRequisition.send("DELETE", f"/corporates/{corp_key}/members/{member_key}", headers=headers_owner)
        
        # View (should fail)
        resp2 = ClientRequisition.send("GET", f"/corporates/{corp_key}", headers=headers_member)
        assert resp2.response_status == 403

    def test_finance_can_create_account(self):
        """Finance role can create a corporate account"""
        owner_key, owner_token = self._create_and_login_customer()
        finance_key, finance_token = self._create_and_login_customer()
        corp_key = self._create_corporate(owner_token)
        
        headers_owner = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {owner_token}"}
        ClientRequisition.send("POST", f"/corporates/{corp_key}/members", payload={"customer_key": finance_key, "role": "finance"}, headers=headers_owner)
        
        headers_finance = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {finance_token}"}
        resp = ClientRequisition.send("POST", f"/corporates/{corp_key}/accounts", headers=headers_finance)
        
        assert resp.response_status == 201
        assert "account_key" in resp.response_json
