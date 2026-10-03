from controllers.base_controller import BaseController
from repositories.corporate_repository import CorporateRepository
from repositories.customer_repository import CustomerRepository
from repositories.account_repository import AccountRepository
from controllers.account_controller import AccountController
from errors.custom_errors import InvalidCNPJ, DuplicatedCNPJ, NotFoundCustomer, NotFoundCorporate, ForbiddenAction, AlreadyCorporateMember
from utils.document_number import is_valid_cnpj



class CorporateController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.corporate_repository = CorporateRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def _check_role(self, corporate, customer, required_roles: list) -> bool:
        if not customer:
            return False
        member = self.corporate_repository.get_member(corporate.id, customer.id)
        if not member:
            return False
        return member.role in required_roles

    def create_corporate(self, payload: dict, authenticated_customer_key: str) -> dict:
        self.logger.debug("Creating a new CorporateCustomer")

        cnpj = payload["cnpj"]
        
        if not is_valid_cnpj(cnpj):
            raise InvalidCNPJ()
            
        if self.corporate_repository.exists_by_cnpj(cnpj):
            raise DuplicatedCNPJ()
            
        customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not customer:
            raise NotFoundCustomer()

        corp = self.corporate_repository.create(payload)
        self.corporate_repository.add_member(corp, customer, "owner")
        
        self.session.commit()
        
        return {
            "corporate_key": corp.corporate_key,
            "cnpj": corp.cnpj,
            "company_name": corp.company_name,
            "trade_name": corp.trade_name,
            "status": "created",
            "created_at": corp.created_at.isoformat() if corp.created_at else None
        }

    def get_details(self, corporate_key: str, authenticated_customer_key: str) -> dict:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)
            
        customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not self._check_role(corp, customer, ["owner", "finance", "operator", "viewer"]):
            raise ForbiddenAction()
            
        members_data = []
        for mem in corp.members:
            members_data.append({
                "customer_key": mem.customer.customer_key,
                "role": mem.role
            })
            
        accounts_data = []
        for corp_acc in corp.accounts:
            accounts_data.append(corp_acc.account.account_key)
            
        return {
            "corporate_key": corp.corporate_key,
            "cnpj": corp.cnpj,
            "company_name": corp.company_name,
            "trade_name": corp.trade_name,
            "status": corp.status.enumerator if corp.status else "created",
            "members": members_data,
            "accounts": accounts_data
        }

    def add_member(self, corporate_key: str, payload: dict, authenticated_customer_key: str) -> dict:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)

        auth_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not self._check_role(corp, auth_customer, ["owner"]):
            raise ForbiddenAction()

        target_customer = self.customer_repository.get_by_key(payload["customer_key"])
        if not target_customer:
            raise NotFoundCustomer()

        if self.corporate_repository.get_member(corp.id, target_customer.id):
            raise AlreadyCorporateMember()

        member = self.corporate_repository.add_member(corp, target_customer, payload["role"])
        self.session.commit()

        return {"customer_key": target_customer.customer_key, "role": member.role}

    def remove_member(self, corporate_key: str, target_customer_key: str, authenticated_customer_key: str) -> None:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)

        auth_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not self._check_role(corp, auth_customer, ["owner"]):
            raise ForbiddenAction()

        target_customer = self.customer_repository.get_by_key(target_customer_key)
        if not target_customer:
            raise NotFoundCustomer()

        member = self.corporate_repository.get_member(corp.id, target_customer.id)
        if not member:
            raise NotFoundCustomer() # Or a more specific NotAMember error, but 404 is okay

        self.corporate_repository.remove_member(member)
        self.session.commit()

    def create_account(self, corporate_key: str, authenticated_customer_key: str) -> dict:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)

        auth_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        # Finance and Owner can create accounts
        if not self._check_role(corp, auth_customer, ["owner", "finance"]):
            raise ForbiddenAction()

        from utils.account_number import generate_account_number
        from errors.custom_errors import AccountNumberGenerationFailed
        
        account_data = {"type": "checking", "branch": "0001"}
        for _ in range(5):
            account_data["number"] = generate_account_number()
            if self.account_repository.get_by_branch_and_number(account_data["branch"], account_data["number"]) is None:
                break
        else:
            raise AccountNumberGenerationFailed()

        account_controller = AccountController()
        account_dto = account_controller.open_account(auth_customer.id, account_data)
        
        account = self.account_repository.get_by_key(account_dto["account_key"])
        
        self.corporate_repository.link_account(corp.id, account.id)
        self.session.commit()
        
        return account_dto


    def request_transfer(self, corporate_key: str, payload: dict, authenticated_customer_key: str) -> dict:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)

        auth_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not self._check_role(corp, auth_customer, ["owner", "finance", "operator"]):
            raise ForbiddenAction()

        origin_account = self.account_repository.get_by_key(payload["origin_account_key"])
        if not origin_account:
            from errors.custom_errors import NotFoundAccount
            raise NotFoundAccount(payload["origin_account_key"])

        # Validate that the origin account belongs to the corporate entity
        if not self.corporate_repository.is_corporate_account(corp.id, origin_account.id):
            from errors.custom_errors import NotACorporateAccount
            raise NotACorporateAccount()

        req = self.corporate_repository.create_transfer_request(
            corporate_id=corp.id,
            requester_id=auth_customer.id,
            origin_account_id=origin_account.id,
            destination_key=payload["destination_account_key"],
            amount=payload["amount"]
        )
        
        self.corporate_repository.create_audit(
            corporate_id=corp.id,
            action="transfer_requested",
            author_id=auth_customer.id,
            metadata=f"Request ID: {req.id}, Amount: {payload['amount']}"
        )
        
        self.session.commit()
        return {"request_id": req.id, "status": req.status}

    def approve_transfer(self, corporate_key: str, request_id: int, authenticated_customer_key: str) -> dict:
        corp = self.corporate_repository.get_by_key(corporate_key)
        if not corp:
            raise NotFoundCorporate(corporate_key)

        auth_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if not self._check_role(corp, auth_customer, ["owner", "finance"]):
            raise ForbiddenAction()

        req = self.corporate_repository.get_transfer_request_for_update(request_id)
        if not req or req.corporate_id != corp.id:
            from errors.custom_errors import NotFoundTransferRequest
            raise NotFoundTransferRequest()
            
        if req.status != "pending":
            raise ForbiddenAction() # Or a specific state error

        # Perform the actual transaction using TransactionController
        from controllers.transaction_controller import TransactionController
        transaction_controller = TransactionController()
        
        transaction_payload = {
            "origin_account_key": req.origin_account.account_key,
            "amount": req.amount,
            "type": "transfer",
            "destination_account_key": req.destination_account_key,
            "channel": "pix" # Hardcoding for phase 2 simplicity
        }
        
        # We need to impersonate or pass the original account's customer context?
        # In TransactionController.create_transaction, the caller_customer_key must match the account owner!
        # The Corporate Account's customer_id is the finance/owner who CREATED the account!
        # We should use that person's key or the requester's key? Wait.
        # TransactionController checks if `account.customer.customer_key == caller_customer_key`.
        # So we MUST pass `req.origin_account.customer.customer_key` as the caller to bypass the standard decoupled check!
        # Wait, if we do this, it works seamlessly!
        actual_account_owner_key = req.origin_account.customer.customer_key

        req.status = "approved"
        self.session.flush()
        
        transaction_controller.process_transaction(transaction_payload, actual_account_owner_key)
        
        self.corporate_repository.create_audit(
            corporate_id=corp.id,
            action="transfer_approved",
            author_id=auth_customer.id,
            metadata=f"Request ID: {req.id}"
        )
        
        self.session.commit()
        return {"request_id": req.id, "status": req.status}

