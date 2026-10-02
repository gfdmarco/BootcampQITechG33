from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import ClientRequisition
from tests.utils.random_generator import RandomGenerator

class TestCorporateTransfers:
    def _create_and_login_customer(self):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        return response["customer_key"], login_response["access_token"]

    def _setup_corporate_scenario(self):
        # 1. Create Users
        owner_key, owner_token = self._create_and_login_customer()
        finance_key, finance_token = self._create_and_login_customer()
        operator_key, operator_token = self._create_and_login_customer()
        viewer_key, viewer_token = self._create_and_login_customer()

        # 2. Create Corporate
        cnpj = RandomGenerator.generate_cnpj().replace(".", "").replace("/", "").replace("-", "")
        payload = {"cnpj": cnpj, "company_name": "Transfers Corp"}
        headers_owner = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {owner_token}"}
        resp = ClientRequisition.send("POST", "/corporates", payload=payload, headers=headers_owner)
        corp_key = resp.response_json["corporate_key"]

        # 3. Add Members
        for m_key, role in [(finance_key, "finance"), (operator_key, "operator"), (viewer_key, "viewer")]:
            ClientRequisition.send(
                "POST", f"/corporates/{corp_key}/members", 
                payload={"customer_key": m_key, "role": role}, 
                headers=headers_owner
            )

        # 4. Open Corporate Account
        headers_finance = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {finance_token}"}
        resp_acc = ClientRequisition.send("POST", f"/corporates/{corp_key}/accounts", headers=headers_finance)
        corp_acc_key = resp_acc.response_json["account_key"]

        # 5. Deposit into Corporate Account via direct endpoint (if needed) or just assume it works
        # Standard deposit
        dep_payload = {"destination_account_key": corp_acc_key, "amount": 5000, "type": "deposit", "channel": "pix"}
        ClientRequisition.send("POST", "/transactions", payload=dep_payload, headers=headers_finance)

        # 6. Target Account (Regular)
        target_customer_key, target_token = self._create_and_login_customer()
        resp_target_acc = ClientRequisition.send("POST", f"/customers/{target_customer_key}/accounts", payload={"type": "checking"}, headers={"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {target_token}"})
        target_acc_key = resp_target_acc.response_json["account_key"]

        return {
            "corp_key": corp_key,
            "corp_acc_key": corp_acc_key,
            "target_acc_key": target_acc_key,
            "tokens": {
                "owner": owner_token,
                "finance": finance_token,
                "operator": operator_token,
                "viewer": viewer_token,
            }
        }

    def test_operator_requests_transfer_is_pending(self):
        env = self._setup_corporate_scenario()
        
        payload = {
            "origin_account_key": env["corp_acc_key"],
            "destination_account_key": env["target_acc_key"],
            "amount": 1000
        }
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['operator']}"}
        resp = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers", payload=payload, headers=headers)
        
        assert resp.response_status == 201
        assert resp.response_json["status"] == "pending"
        
        # Verify balance remains unchanged
        headers_finance = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['finance']}"}
        bal_resp = ClientRequisition.send("GET", f"/accounts/{env['corp_acc_key']}/balance", headers=headers_finance)
        assert bal_resp.response_json["balance"] == 5000

    def test_viewer_cannot_request_transfer(self):
        env = self._setup_corporate_scenario()
        
        payload = {
            "origin_account_key": env["corp_acc_key"],
            "destination_account_key": env["target_acc_key"],
            "amount": 1000
        }
        headers = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['viewer']}"}
        resp = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers", payload=payload, headers=headers)
        
        assert resp.response_status == 403

    def test_operator_cannot_approve(self):
        env = self._setup_corporate_scenario()
        
        # 1. Operator requests
        payload = {"origin_account_key": env["corp_acc_key"], "destination_account_key": env["target_acc_key"], "amount": 1000}
        headers_op = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['operator']}"}
        resp = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers", payload=payload, headers=headers_op)
        req_id = resp.response_json["request_id"]
        
        # 2. Operator tries to approve
        resp_app = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers/{req_id}/approve", headers=headers_op)
        assert resp_app.response_status == 403

    def test_finance_approves_transfer(self):
        env = self._setup_corporate_scenario()
        
        # 1. Operator requests
        payload = {"origin_account_key": env["corp_acc_key"], "destination_account_key": env["target_acc_key"], "amount": 1000}
        headers_op = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['operator']}"}
        resp = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers", payload=payload, headers=headers_op)
        req_id = resp.response_json["request_id"]
        
        # 2. Finance approves
        headers_fin = {"INTERNAL-TOKEN": "default_token", "Authorization": f"Bearer {env['tokens']['finance']}"}
        resp_app = ClientRequisition.send("POST", f"/corporates/{env['corp_key']}/transfers/{req_id}/approve", headers=headers_fin)
        assert resp_app.response_status == 200
        assert resp_app.response_json["status"] == "approved"
        
        # 3. Check balances
        bal_resp = ClientRequisition.send("GET", f"/accounts/{env['corp_acc_key']}/balance", headers=headers_fin)
        assert bal_resp.response_json["balance"] == 4000
