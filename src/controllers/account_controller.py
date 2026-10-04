from datetime import date

from controllers.base_controller import BaseController
from dtos import AccountDTO, TransactionDTO
from errors import (
    InvalidIdempotencyKey,
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidDate,
    InvalidDocumentNumber,
    InvalidParameter,
    DuplicatedAccount,
    ForbiddenAction,
    NotFoundCustomer,
    CustomerAccountLimitReached,
    NotFoundAccount,
    AccountInvalidStatusTransition,
    AccountHasBalance,
    InvalidAmount
)
from models import Account, AccountStatus, Customer, CustomerStatus
from repositories import AccountRepository, TransactionRepository, CustomerRepository
from utils.idempotency import lock_idempotency_key

MAX_ACCOUNTS_PER_CUSTOMER = 5

ALLOWED_STATUS_TRANSITIONS = {
    AccountStatus.ACTIVE: [AccountStatus.BLOCKED, AccountStatus.CLOSED],
    AccountStatus.BLOCKED: [AccountStatus.ACTIVE, AccountStatus.CLOSED],
    AccountStatus.CLOSED: [],
}

class AccountController(BaseController):
    """Regras de negócio em que as contas se baseiam"""

    def __init__(self) -> None:
        super().__init__(__name__)
        self.customer_repository = CustomerRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

    def get_account_aux(self, account_key: str, caller_customer_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)
        caller_customer = self.customer_repository.get_by_key(caller_customer_key)
        if account is None:
            raise NotFoundAccount(account_key)
        if caller_customer is None:
            raise NotFoundCustomer(caller_customer_key)
        if caller_customer.id != account.customer_id:
            raise ForbiddenAction()

        return account

    def open_account(self, customer_id: int, account_data: dict, idempotency_key: str = None) -> dict:
        """Abre a conta. Idempotente quando vem `idempotency_key`.

        A chave vem do cliente (header Idempotency-Key, obrigatório em
        POST /customers/{key}/accounts). Não dá para derivar de agência e
        número: o número é sorteado a cada pedido, então um retry sortearia
        outro número, outra chave — e abriria uma segunda conta.

        Contas abertas por dentro do sistema (conta PJ) chegam sem chave.
        """
        branch = account_data["branch"]
        number = account_data["number"]

        if idempotency_key is not None:
            lock_idempotency_key(self.session, "account", idempotency_key)

            existing = self.account_repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                # Mesma chave, mesmo dono e mesmo tipo: é a repetição do
                # pedido. Devolve a conta da primeira vez, sem abrir outra
                # e sem contar de novo no limite de 5 contas.
                if existing.customer_id != customer_id or existing.type != account_data["type"]:
                    raise InvalidIdempotencyKey()
                existing_dto = AccountDTO.obj_to_dict(existing)
                self._log_return("Abertura de conta repetida: devolvendo a original", existing_dto)
                return existing_dto

        accounts_count = self.account_repository.count_active_by_customer(customer_id)
        if accounts_count >= MAX_ACCOUNTS_PER_CUSTOMER:
            raise CustomerAccountLimitReached()

        if self.account_repository.get_by_branch_and_number(branch, number) is not None:
            raise DuplicatedAccount(branch, number)

        account_data["customer_id"] = customer_id
        account_data["idempotency_key"] = idempotency_key
        account = self.account_repository.create(account_data)
        self.account_repository.update_status(account, AccountStatus.ACTIVE)

        self.session.flush()
        account_dto = AccountDTO.obj_to_dict(account)

        self.session.commit()
        self._log_return("Conta aberta", account_dto)
        return account_dto

    def get_balance(self, account_key: str, caller_customer_key: str) -> int:
        account = self.get_account_aux(account_key, caller_customer_key)
        result = account.balance
        self._log_return("Saldo consultado", {"account_key": account_key})   # o valor do saldo não vai para o log
        return result

    def get_by_key(self, account_key: str, caller_customer_key: str) -> dict:
        account = self.get_account_aux(account_key, caller_customer_key)
        result = AccountDTO.obj_to_dict(account)
        self._log_return("Conta consultada", result)
        return result

    def update_status(self, account_key: str, new_status: str, caller_customer_key: str) -> dict:
        account = self.get_account_aux(account_key, caller_customer_key)
        
        old_status = account.status.enumerator

        if new_status not in ALLOWED_STATUS_TRANSITIONS.get(old_status, []):
            raise AccountInvalidStatusTransition(old_status, new_status)

        if new_status == AccountStatus.CLOSED and account.balance != 0:
            raise AccountHasBalance(account_key, account.balance)

        self.account_repository.update_status(account, new_status)

        self.session.flush()
        account_dto = AccountDTO.obj_to_dict(account)

        _owner_key = account.customer.customer_key.strip()
        _new_status = new_status.value if hasattr(new_status, "value") else new_status
        notification_event_keys = []

        if _new_status in ("blocked", "active"):
            from controllers.notification_controller import NotificationController

            notifier = NotificationController()
            notification_event_keys = notifier.enqueue_account_status(_owner_key, _new_status)

        self.session.commit()

        # Notificacao fire-and-forget: nunca quebra a mudanca de status.
        if notification_event_keys:
            try:
                notifier.process_event_keys(notification_event_keys)
                notifier.session.commit()
            except Exception:
                self.logger.exception("Falha ao criar notificacao de conta")
                try:
                    self.session.rollback()
                except Exception:
                    pass

        result = account_dto
        self._log_return("Status da conta alterado", result)
        return result

    def _parseDate(self, rawDate: str) -> date:
        """Converte a data, ou recusa com 422 em vez de 500.
        """
        try:
            return date.fromisoformat(rawDate)
        except ValueError:
            raise InvalidDate(rawDate)

    def get_list(self, limit: int, offset: int, filters: dict, caller_customer_key: str) -> dict:
        caller_customer = self.customer_repository.get_by_key(caller_customer_key)

        if caller_customer is None:
            raise NotFoundCustomer(caller_customer_key)
        
        filters["customer_id"] = caller_customer.id

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

        account_list = self.account_repository.list_page(limit, offset, filters)

        # Pedimos um a mais que o limite só pra saber se existe próxima
        # página. Se veio o extra, ele não entra na resposta.
        is_last_page = True
        if len(account_list) > limit:
            is_last_page = False
            account_list = account_list[:-1]

        result = {
            "account_list_dto": AccountDTO.list_obj_to_list_dict(account_list),
            "is_last_page": is_last_page,
        }
        self._log_return("Lista de contas retornada", result)
        return result

    def get_statement(self, account_key: str, caller_customer_key: str, limit: int, offset: int, filters: dict) -> dict:
        account = self.get_account_aux(account_key, caller_customer_key)
        filters["account_id"] = account.id

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

        result = {
            "transaction_list_dto": TransactionDTO.list_obj_to_list_dict(transaction_list),
            "is_last_page": is_last_page,
        }
        self._log_return("Extrato retornado", result)
        return result
