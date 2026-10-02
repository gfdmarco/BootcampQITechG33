import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))
os.environ["RISK_ENGINE_URL"] = "http://localhost:8001"
from controllers.loan_controller import LoanController
from database import open_context, clear_context
from tests.utils import PayloadGenerator, RequestGenerator
from errors.custom_errors import InvalidLoanAmount

class TestLoanControllerDirect:
    def setup_method(self):
        self.context = open_context()
        self.context.get_or_create_session()
        
    def teardown_method(self):
        if self.context.db_session:
            self.context.db_session.rollback()
            self.context.db_session.close()
        clear_context()
    def _create_account(self):
        payload = PayloadGenerator.create_customer_payload()
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 201
        customer_key = response["customer_key"]

        login_payload = {
            "document_number": payload["document_number"],
            "password": payload["password"]
        }
        _, login_response = RequestGenerator.POST_auth_login(login_payload)
        token = login_response["access_token"]

        # Create account
        status, response = RequestGenerator.POST_customer_account(
            customer_key, {"type": "checking"}, token
        )
        assert status == 201
        account_key = response["account_key"]
        
        return customer_key, account_key

    def test_simulate_loan_invalid_amount(self):
        """Testa que valores inválidos (<=0) falham imediatamente sem bater no Motor de Risco"""
        customer_key, account_key = self._create_account()
        
        controller = LoanController()
        
        with pytest.raises(InvalidLoanAmount):
            controller.simulate_loan(
                account_key=account_key,
                requested_amount=0,
                installments_count=3,
                authenticated_customer_key=customer_key
            )
            
        with pytest.raises(InvalidLoanAmount):
            controller.simulate_loan(
                account_key=account_key,
                requested_amount=-5000,
                installments_count=3,
                authenticated_customer_key=customer_key
            )

    def test_create_loan_success_math_and_db(self):
        """Testa a criação real do empréstimo direto pelo Controller e persistência no BD"""
        customer_key, account_key = self._create_account()
        controller = LoanController()
        
        # Como o Mock do Risk Engine responde 'low' para clientes sem o prefixo 'high', 
        # esperamos juros de 1.5% (15 na base 1000)
        loan = controller.create_loan(
            account_key=account_key,
            requested_amount=100000,
            installments_count=3,
            authenticated_customer_key=customer_key
        )
        
        assert loan["requested_amount"] == 100000
        assert loan["total_amount_due"] == 101500  # 1.5% de juros
        assert loan["interest_rate"] == 15
        assert len(loan["installments"]) == 3
        
        # Divisão das parcelas: 101500 / 3 = 33833.33 -> 33833, 33833, 33834
        assert loan["installments"][0]["amount"] == 33833
        assert loan["installments"][1]["amount"] == 33833
        assert loan["installments"][2]["amount"] == 33834
        assert loan["installments"][0]["status"] == "pending"
