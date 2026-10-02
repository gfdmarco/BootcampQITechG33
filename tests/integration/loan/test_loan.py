from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.request_generator import ClientRequisition, INTERNAL_TOKEN

class TestLoanEndpoints:
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

    def _create_account(self, customer_key, access_token):
        status, response = RequestGenerator.POST_customer_account(
            customer_key, {"type": "checking"}, access_token
        )
        assert status == 201
        return response["account_key"]
        
    def POST_simulate_loan(self, payload: dict, access_token: str):
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN, "Authorization": f"Bearer {access_token}"}
        response = ClientRequisition.send("POST", "/loans/simulate", payload=payload, headers=headers)
        return response.response_status, response.response_json

    def POST_create_loan(self, payload: dict, access_token: str):
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN, "Authorization": f"Bearer {access_token}"}
        response = ClientRequisition.send("POST", "/loans", payload=payload, headers=headers)
        return response.response_status, response.response_json

    def POST_pay_installment(self, loan_key: str, installment_id: int, access_token: str):
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN, "Authorization": f"Bearer {access_token}"}
        response = ClientRequisition.send(
            "POST", 
            f"/loans/{loan_key}/installments/{installment_id}/pay", 
            headers=headers
        )
        return response.response_status, response.response_json

    def test_simulate_loan(self):
        """200; simulates loan and returns calculated installments"""
        customer_key, token = self._create_and_login_customer()
        account_key = self._create_account(customer_key, token)

        payload = {
            "account_key": account_key,
            "requested_amount": 100000,
            "installments_count": 3
        }

        status, response = self.POST_simulate_loan(payload, token)
        assert status == 200
        
        # Risk engine will return "low" (1.5% interest) because customer_key doesn't start with "high"
        assert "total_amount_due" in response
        assert "installments" in response
        assert len(response["installments"]) == 3
        assert response["total_amount_due"] == 101500
        assert response["installments"][0]["amount"] == 33833

    def test_create_loan_success(self):
        """201; creates a loan and credits account"""
        customer_key, token = self._create_and_login_customer()
        account_key = self._create_account(customer_key, token)

        payload = {
            "account_key": account_key,
            "requested_amount": 100000,
            "installments_count": 3
        }
        
        status, response = self.POST_create_loan(payload, token)
        assert status == 201
        assert "loan_key" in response
        
        # Check if the account was credited
        status, balance_resp = RequestGenerator.GET_account(account_key, token)
        assert status == 200
        assert balance_resp["balance"] == 100000

    def test_pay_installment(self):
        """204; pays an installment and debits the account"""
        customer_key, token = self._create_and_login_customer()
        account_key = self._create_account(customer_key, token)

        payload = {
            "account_key": account_key,
            "requested_amount": 100000,
            "installments_count": 1
        }
        
        # Create a loan
        status, resp = self.POST_create_loan(payload, token)
        assert status == 201
        loan_key = resp["loan_key"]
        installment_id = resp["installments"][0]["id"]
        
        # Trying to pay without enough balance: 100000 < 103000
        status, _ = self.POST_pay_installment(loan_key, installment_id, token)
        assert status == 422 # Insufficient balance
        
        # Deposit money to be able to pay
        deposit_payload = {
            "type": "deposit",
            "amount": 10000,
            "destination_account_key": account_key,
            "channel": "pix"
        }
        status, _ = RequestGenerator.POST_transaction(deposit_payload, token)
        assert status == 201
        
        # Retry payment
        status, pay_resp = self.POST_pay_installment(loan_key, installment_id, token)
        assert status == 204 # No content on success
