from uuid import uuid4

from database import Context
from models import BankSlip, BankSlipStatus, BankSlipStatusEvent

class BankSlipRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_status(self, enumerator: str) -> BankSlipStatus:
        return (
            self.session.query(BankSlipStatus)
            .filter(BankSlipStatus.enumerator == enumerator)
            .first()
        )

    def create(self, account_id: int, bank_slip_data: dict) -> BankSlip:
        # o customer_id chega por responsabilidade do controller para construir o data corretamente
        bank_slip = BankSlip()

        bank_slip.bank_slip_key = str(uuid4())
        bank_slip.account_id = account_id
        bank_slip.amount = bank_slip_data["amount"]
        bank_slip.expiration_date = bank_slip_data["expiration_date"]

        # pela relationship, o status_id é construído pelo SQLAlchemy
        bank_slip.status = self.get_status(BankSlipStatus.PENDING)

        self.session.add(bank_slip)
        return bank_slip

    def update_status(self, bank_slip: BankSlip, new_status_enumerator: str, reason: str = None) -> None:
        old_status = bank_slip.status
        new_status = self.get_status(new_status_enumerator)
        bank_slip.status = new_status

        new_status_event = BankSlipStatusEvent()
        new_status_event.to_status = new_status
        new_status_event.from_status = old_status
        new_status_event.reason = reason

        bank_slip.status_events.append(new_status_event)

    def get_by_key(self, bank_slip_key: str) -> BankSlip:
        return self.session.query(BankSlip).filter(BankSlip.bank_slip_key == bank_slip_key).first()

    def get_by_key_for_update(self, bank_slip_key: str) -> BankSlip:
        """Busca TRAVANDO a linha até o commit (SELECT ... FOR UPDATE)."""
        return (
            self.session.query(BankSlip)
            .filter(BankSlip.bank_slip_key == bank_slip_key)
            .with_for_update()
            .populate_existing()
            .first()
        )
    
    def list_by_account(self, account_id: int, limit: int, offset: int) -> list:
        return (
            self.session.query(BankSlip)
            .filter(BankSlip.account_id == account_id)
            .order_by(BankSlip.created_at.desc(), BankSlip.id.desc())
            .limit(limit + 1)
            .offset(offset)
            .all()
        )