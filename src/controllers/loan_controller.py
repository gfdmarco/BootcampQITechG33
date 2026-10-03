import uuid
from datetime import datetime, timedelta

from controllers.base_controller import BaseController
from models.loan import Loan
from models.loan_installment import LoanInstallment
from models import AccountStatus, TransactionStatus
from repositories import AccountRepository, TransactionRepository
from connectors.risk_engine_connector import RiskEngineConnector
from utils.clock import business_now
from errors.custom_errors import HighRiskProfile, InsufficientBalanceForInstallment, InstallmentNotFound, NotFoundAccount, InvalidLoanAmount
from errors import ForbiddenAction



class LoanController(BaseController):
    """
    Business rules for the Loans domain. Orchestrates Risk evaluation,
    loan disbursement, and installment payments using the core AccountRepository.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)
        self.risk_connector = RiskEngineConnector()

    def simulate_loan(self, account_key: str, requested_amount: int, installments_count: int, authenticated_customer_key: str) -> dict:
        """Calculates interest and installment distribution without saving."""
        
        # 1. Validate amount
        if requested_amount <= 0:
            raise InvalidLoanAmount()
            
        # 2. Verify account exists and belongs to the authenticated user
        account = self.account_repository.get_by_key(account_key)
        if not account:
            raise NotFoundAccount(account_key)
            
        if account.customer.customer_key != authenticated_customer_key:
            raise ForbiddenAction()

        if account.status.enumerator != AccountStatus.ACTIVE:
            raise ForbiddenAction()
            
        # 2. Risk check
        risk_score = self.risk_connector.get_customer_risk_score(account.customer.customer_key)
        
        if risk_score == "high":
            raise HighRiskProfile()
            
        interest_rate = 15 if risk_score == "low" else 30  # tenths of percent
        
        # 3. Math (integers only)
        interest_amount = (requested_amount * interest_rate) // 1000
        total_amount_due = requested_amount + interest_amount
        
        base_installment = total_amount_due // installments_count
        remainder = total_amount_due % installments_count
        
        installments = []
        for i in range(installments_count):
            amount = base_installment
            if i == installments_count - 1:
                amount += remainder
                
            installments.append({
                "installment_number": i + 1,
                "amount": amount
            })
            
        return {
            "requested_amount": requested_amount,
            "total_amount_due": total_amount_due,
            "interest_rate": interest_rate,
            "installments_count": installments_count,
            "installments": installments
        }

    def create_loan(self, account_key: str, requested_amount: int, installments_count: int, authenticated_customer_key: str) -> dict:
        """Disburses a loan to the account after risk approval."""
        
        # Reuse simulation logic for pure math and risk evaluation
        sim_data = self.simulate_loan(account_key, requested_amount, installments_count, authenticated_customer_key)
        
        account = self.account_repository.get_by_key(account_key)
        
        loan = Loan(
            loan_key=str(uuid.uuid4()),
            account_id=account.id,
            requested_amount=requested_amount,
            total_amount_due=sim_data["total_amount_due"],
            interest_rate=sim_data["interest_rate"],
            status="active"
        )
        
        # Create installments
        now = business_now()
        for i, sim_inst in enumerate(sim_data["installments"]):
            inst = LoanInstallment(
                installment_number=sim_inst["installment_number"],
                amount=sim_inst["amount"],
                due_date=now + timedelta(days=30 * (i + 1)),
                status="pending"
            )
            loan.installments.append(inst)
            
        # Disburse the money using the strictly decoupled existing mechanic
        self.account_repository.credit(account.id, requested_amount)

        transaction = self.transaction_repository.create_transaction({
            "origin_account": None,
            "destination_account": account,
            "amount": requested_amount,
            "fee_amount": 0,
            "type": "deposit",
            "channel": "loan",
        })
        self.transaction_repository.update_status(transaction, TransactionStatus.CONFIRMED, reason="Loan disbursed")
        
        self.session.add(loan)
        self.session.commit()
        
        return {
            "loan_key": loan.loan_key,
            "requested_amount": loan.requested_amount,
            "total_amount_due": loan.total_amount_due,
            "interest_rate": loan.interest_rate,
            "installments": [
                {
                    "id": inst.id,
                    "installment_number": inst.installment_number,
                    "amount": inst.amount,
                    "due_date": inst.due_date.isoformat(),
                    "status": inst.status
                }
                for inst in loan.installments
            ]
        }

    def pay_installment(self, loan_key: str, installment_id: int, authenticated_customer_key: str) -> None:
        """Collects money for an installment via debit."""
        
        # Find installment
        installment = self.session.query(LoanInstallment).join(Loan).filter(
            Loan.loan_key == loan_key,
            LoanInstallment.id == installment_id,
            LoanInstallment.status == "pending"
        ).with_for_update().populate_existing().first()
        
        if not installment:
            raise InstallmentNotFound()
            
        account = installment.loan.account
        
        if account.customer.customer_key != authenticated_customer_key:
            raise ForbiddenAction()
            
        # Collect money
        success = self.account_repository.debit(account.id, installment.amount)
        if not success:
            raise InsufficientBalanceForInstallment()

        bank_account = self.account_repository.get_bank_account()
        self.account_repository.credit(bank_account.id, installment.amount)

        payment = self.transaction_repository.create_transaction({
            "origin_account": account,
            "destination_account": bank_account,
            "amount": installment.amount,
            "fee_amount": 0,
            "type": "transfer",
            "channel": "loan",
        })
        self.transaction_repository.update_status(
            payment,
            TransactionStatus.CONFIRMED,
            reason=f"Loan installment {installment.installment_number} paid",
        )
            
        installment.status = "paid"
        
        # Check if all are paid
        pending_count = self.session.query(LoanInstallment).filter(
            LoanInstallment.loan_id == installment.loan_id,
            LoanInstallment.status == "pending"
        ).count()
        
        if pending_count == 0:
            installment.loan.status = "paid"
            
        self.session.commit()
