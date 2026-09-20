from datetime import date

from controllers.base_controller import BaseController
from dtos import AccountDTO, TransactionDTO
from errors import (
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidDate,
    InvalidDocumentNumber,
    InvalidParameter,
    NotFoundSampleEntity,
    SampleEntityFinalStatus,
    UnderageSampleEntity,
    DuplicatedAccount,
    ForbiddenAction,
    NotFoundCustomer,
    CustomerAccountLimitReached,
    NotFoundAccount
)
from models import Account, AccountStatus, Customer, CustomerStatus
from repositories import AccountRepository, TransactionRepository, CustomerRepository

MAX_ACCOUNTS_PER_CUSTOMER = 3

class AccountController(BaseController):
    """Regras de negócio em que as contas se baseiam"""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def open_account(self, customer_id: int, account_data: dict) -> dict:
        branch = account_data["branch"]
        number = account_data["number"]

        accounts_count = self.account_repository.count_active_by_customer(customer_id)
        if accounts_count >= MAX_ACCOUNTS_PER_CUSTOMER:
            raise CustomerAccountLimitReached(customer_id, MAX_ACCOUNTS_PER_CUSTOMER)

        if self.account_repository.get_by_branch_and_number(branch, number) is not None:
            raise DuplicatedAccount(branch, number)

        account_data["customer_id"] = customer_id
        account = self.account_repository.create(account_data)
        self.account_repository.update_status(account, AccountStatus.ACTIVE)

        account_dto = AccountDTO.obj_to_dict(account)
        
        return account_dto

    def get_balance(self, customer_key: str, account_key: str) -> int:
        customer = self.customer_repository.get_by_key(customer_key)
        if customer is None:
            raise NotFoundCustomer(customer_key)
        
        account = self.account_repository.get_by_key(account_key)

        if account is None:
            raise NotFoundAccount(account_key)
        
        if customer.id != account.customer.id:
            raise ForbiddenAction()

        return account.balance

    def get_by_key(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)

        if account is None:
            raise NotFoundAccount(account_key)

        return AccountDTO.obj_to_dict(account)

    def finish_account(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)
        customer = account.customer

        balance = self.get_balance(customer.customer_key, account_key)
        if balance != 0 or account.status.enumerator != AccountStatus.ACTIVE:
            raise SampleEntityFinalStatus(account.status.enumerator, new_status=AccountStatus.CLOSED)

        self.account_repository.update_status(account, AccountStatus.CLOSED)

        account_dto = AccountDTO.only_obj_key(account)
        self.session.commit()

        return account_dto
    
    def block_account(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)

        if account.status.enumerator != AccountStatus.ACTIVE:
            raise SampleEntityFinalStatus(account.status.enumerator, AccountStatus.BLOCKED)

        self.account_repository.update_status(account, AccountStatus.BLOCKED)

        account_dto = AccountDTO.only_obj_key(account)
        self.session.commit()

        return account_dto

    def unlock_account(self, account_key: str) -> dict:
        # ainda precisamos pensar quando que podemos liberar o desbloqueamento
        account = self.account_repository.get_by_key(account_key)

        if account.status.enumerator != AccountStatus.BLOCKED:
            raise SampleEntityFinalStatus(account.status.enumerator, AccountStatus.ACTIVE)

        self.account_repository.update_status(account, AccountStatus.ACTIVE)

        account_dto = AccountDTO.only_obj_key(account)
        self.session.commit()

        return account_dto

    def _parseDate(self, rawDate: str) -> date:
        """Converte a data, ou recusa com 422 em vez de 500.
        """
        try:
            return date.fromisoformat(rawDate)
        except ValueError:
            raise InvalidDate(rawDate)

    def get_list(self, limit: int, offset: int, filters: dict) -> dict:
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")

        if date_from is not None:
            date_from = self._parse_date(date_from)
            filters["date_from"] = date_from

        if date_to is not None:
            date_to = self._parse_date(date_to)
            filters["date_to"] = date_to

        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise InvalidParameter(
                    f"date_from ({date_from}) is after date_to ({date_to})"
                )

        account_list = self.account_repository.list_page(limit, offset, filters)

        # Pedimos um a mais que o limite só pra saber se existe próxima
        # página. Se veio o extra, ele não entra na resposta.
        is_last_page = True
        if len(account_list) > limit:
            is_last_page = False
            account_list = account_list[:-1]

        return {
            "account_list_dto": AccountDTO.list_obj_to_list_dict(account_list),
            "is_last_page": is_last_page,
        }

    def get_statement(self, customer_key: str, limit: int, offset: int, filters: dict) -> dict:
        account_key = filters.get("account_key")
        if account_key is not None:
            customer = self.customer_repository.get_by_key(customer_key)
            if customer is None:
                raise NotFoundCustomer(customer_key)
            account = self.account_repository.get_by_key(account_key)
            if customer.id != account.customer_id:
                raise ForbiddenAction()
            filters["account"] = account

        date_from = filters.get("date_from")
        date_to = filters.get("date_to")

        if date_from is not None:
            date_from = self._parseDate(date_from)
            filters["date_from"] = date_from

        if date_to is not None:
            date_to = self._parseDate(date_to)
            filters["date_to"] = date_to

        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise InvalidParameter(
                    f"date_from ({date_from}) is after date_to ({date_to})"
                )

        transaction_list = self.transaction_repository.list_page(limit, offset, filters)

        # Pedimos um a mais que o limite só pra saber se existe próxima
        # página. Se veio o extra, ele não entra na resposta.
        is_last_page = True
        if len(transaction_list) > limit:
            is_last_page = False
            transaction_list = transaction_list[:-1]

        return {
            "transaction_list_dto": TransactionDTO.list_obj_to_list_dict(transaction_list),
            "is_last_page": is_last_page,
        }