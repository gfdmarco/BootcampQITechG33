from uuid import uuid4

from database import Context
from models import CorporateCustomer, CorporateStatus, CorporateMember, Customer


class CorporateRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_status(self, enumerator: str) -> CorporateStatus:
        return self.session.query(CorporateStatus).filter(
            CorporateStatus.enumerator == enumerator
        ).one()

    def exists_by_cnpj(self, cnpj: str) -> bool:
        return self.session.query(CorporateCustomer).filter(
            CorporateCustomer.cnpj == cnpj
        ).count() > 0

    def get_by_key(self, corporate_key: str) -> CorporateCustomer:
        return self.session.query(CorporateCustomer).filter(
            CorporateCustomer.corporate_key == corporate_key
        ).first()

    def create(self, data: dict) -> CorporateCustomer:
        corp = CorporateCustomer()
        corp.corporate_key = str(uuid4())
        corp.cnpj = data["cnpj"]
        corp.company_name = data["company_name"]
        corp.trade_name = data.get("trade_name")
        corp.status_id = self.get_status(CorporateStatus.CREATED).id

        self.session.add(corp)
        self.session.flush() # flush to get the id if needed
        return corp

    def add_member(self, corporate: CorporateCustomer, customer: Customer, role: str) -> CorporateMember:
        member = CorporateMember()
        member.corporate_id = corporate.id
        member.customer_id = customer.id
        member.role = role
        
        self.session.add(member)
        return member

    def get_member(self, corporate_id: int, customer_id: int) -> CorporateMember:
        return self.session.query(CorporateMember).filter(
            CorporateMember.corporate_id == corporate_id,
            CorporateMember.customer_id == customer_id
        ).first()

    def remove_member(self, member: CorporateMember) -> None:
        self.session.delete(member)

    def link_account(self, corporate_id: int, account_id: int) -> None:
        from models import CorporateAccount
        corp_acc = CorporateAccount()
        corp_acc.corporate_id = corporate_id
        corp_acc.account_id = account_id
        self.session.add(corp_acc)

    def create_transfer_request(self, corporate_id: int, requester_id: int, origin_account_id: int, destination_key: str, amount: int):
        from models import CorporateTransferRequest
        req = CorporateTransferRequest()
        req.corporate_id = corporate_id
        req.requester_customer_id = requester_id
        req.origin_account_id = origin_account_id
        req.destination_account_key = destination_key
        req.amount = amount
        req.status = "pending"
        
        self.session.add(req)
        self.session.flush()
        return req

    def get_transfer_request(self, request_id: int):
        from models import CorporateTransferRequest
        return self.session.query(CorporateTransferRequest).filter(
            CorporateTransferRequest.id == request_id
        ).first()

    def update_transfer_status(self, request_id: int, status: str):
        from models import CorporateTransferRequest
        req = self.get_transfer_request(request_id)
        if req:
            req.status = status
        return req

    def create_audit(self, corporate_id: int, action: str, author_id: int, metadata: str = None):
        from models import CorporateAudit
        audit = CorporateAudit()
        audit.corporate_id = corporate_id
        audit.action = action
        audit.author_id = author_id
        audit.metadata = metadata
        self.session.add(audit)

    def is_corporate_account(self, corporate_id: int, account_id: int) -> bool:
        from models import CorporateAccount
        return self.session.query(CorporateAccount).filter(
            CorporateAccount.corporate_id == corporate_id,
            CorporateAccount.account_id == account_id
        ).count() > 0
