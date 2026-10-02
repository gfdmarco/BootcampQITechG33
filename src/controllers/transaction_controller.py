from controllers.base_controller import BaseController
from dtos import TransactionDTO
from connectors.risk_engine_connector import RiskEngineConnector
from errors import (
    ForbiddenAction,
    InsufficientBalance,
    InvalidParameter,
    InvalidTransactionType,
    NotFoundAccount,
    NotFoundTransaction,
    OriginAccountRequired,
    TransactionFinalStatus,
    NotFoundCustomer
)
from models import Transaction, TransactionStatus, CustomerStatus, AccountStatus
from repositories import (
    AccountRepository,
    FeeRepository,
    TransactionRepository,
    CustomerRepository
)

VALID_TRANSACTION_TYPES = ("deposit", "transfer")


class TransactionController(BaseController):
    """As regras de negócio das transações. Aqui mora o "pode" e o "não pode"."""

    def __init__(self) -> None:
        # Chama a classe mãe para herdar logger, session e context.
        super().__init__(__name__)

        # Passa o 'context' aos repositórios, e não a sessão solta.
        # Só um repositório de transação agora: status e evento
        # histórico moram dentro dele, não em classes à parte.
        self.transaction_repository = TransactionRepository(self.context)
        self.fee_repository = FeeRepository(self.context)
        self.account_repository = AccountRepository(self.context)
        self.customer_repository = CustomerRepository(self.context)
        self.risk_connector = RiskEngineConnector()

    def process_transaction(self, payload: dict, authenticated_customer_key: str) -> dict:
        """
        Confere quem está pedindo, avalia as regras e só então mexe em saldo.

        A ordem aqui não é acidente: tipo de transação e existência das
        contas são perguntas que não dependem de dinheiro nenhum, por
        isso vêm primeiro — igual o CPF é validado antes de qualquer
        escrita no sample. Débito e crédito só acontecem depois que a
        posse da conta de origem já foi confirmada, nunca antes.

        A transação nasce PENDING (o `create_transaction` do
        repositório já cuida disso, sem gerar evento — não há "de
        onde" ela veio). O `update_status` para CONFIRMED, logo
        abaixo, é quem grava o primeiro evento de verdade da trilha:
        "de pending para confirmed".
        """
        self.logger.debug("Processando uma nova transação")

        # Validação via Connector Externo (Anti-Fraud Sidecar)
        self.risk_connector.evaluate_transaction(
            customer_key=authenticated_customer_key,
            amount=payload.get("amount", 0),
            transaction_type=payload.get("channel")
        )

        transaction_type = payload.get("type")
        destination_account_key = payload.get("destination_account_key")

        if transaction_type not in VALID_TRANSACTION_TYPES:
            raise InvalidTransactionType(transaction_type)

        caller_customer = self.customer_repository.get_by_key(authenticated_customer_key)
        if caller_customer is None:
            raise NotFoundCustomer(authenticated_customer_key)
        
        if caller_customer.status.enumerator == CustomerStatus.FAILED:
            raise ForbiddenAction()
        
        # Busca pela chave pública — o controller nunca enxerga o `id`.
        destination_account = self.account_repository.get_by_key(destination_account_key)
        if destination_account is None:
            raise NotFoundAccount(destination_account_key)
        if destination_account.status.enumerator != AccountStatus.ACTIVE:
            raise ForbiddenAction()

        origin_account = None
        fee_amount = 0
        fee_obj = None

        if transaction_type == "deposit":
            # Depósito não tem origem nem tarifa.
            if destination_account.customer_id != caller_customer.id:
                raise ForbiddenAction()
            self.account_repository.credit(destination_account.id, payload["amount"])

        else:  # transfer
            origin_key = payload.get("origin_account_key")
            if not origin_key:
                raise OriginAccountRequired()

            origin_account = self.account_repository.get_by_key(origin_key)
            if origin_account is None:
                raise NotFoundAccount(origin_key)
            
            if origin_account.status.enumerator != AccountStatus.ACTIVE:
                raise ForbiddenAction()

            if origin_account.id == destination_account.id:
                raise InvalidParameter("Origin and Destination accounts cannot be the same.")

            # Comparação feita só entre chaves públicas, navegando pelo
            # relationship do ORM — nunca por `_id`.
            if origin_account.customer.customer_key != authenticated_customer_key:
                raise ForbiddenAction()

            fee_obj = self.fee_repository.get_by_type(payload["channel"])

            # Sem float: percentage é tratado como inteiro (ex.: 2 = 2%).
            # Se o modelo Fee guardar percentage com casas decimais,
            # ajuste esta conta para trabalhar em base inteira maior
            # (ex.: pontos-base) em vez de introduzir float aqui.
            fee_amount = (int(payload["amount"]) * fee_obj.percentage) // 100
            total_debit = int(payload["amount"]) + fee_amount

            # Débito atômico: ou desconta tudo, ou nada é gravado.
            amount = int(payload["amount"])
            if origin_account.id < destination_account.id:
                if not self.account_repository.debit(origin_account.id, total_debit):
                    raise InsufficientBalance()
                self.account_repository.credit(destination_account.id, amount)
            else:
                self.account_repository.credit(destination_account.id, amount)
                if not self.account_repository.debit(origin_account.id, total_debit):
                    raise InsufficientBalance()

        transaction_data = {
            "origin_account": origin_account,
            "destination_account": destination_account,
            "amount": payload["amount"],
            "fee_amount": fee_amount,
            "fee": fee_obj,
            "type": transaction_type,
            "channel": payload["channel"],
        }

        transaction = self.transaction_repository.create_transaction(transaction_data)

        # PENDING -> CONFIRMED. Passa o ENUMERADOR (string), não o
        # objeto: quem busca o TransactionStatus certo é o repositório.
        self.transaction_repository.update_status(
            transaction,
            TransactionStatus.CONFIRMED,
            reason=f"Operação de {transaction_type} realizada com sucesso",
        )

        self.session.flush()
        # Passa pelo DTO antes do commit final.
        transaction_dto = TransactionDTO.only_obj_key(transaction)

        self.session.commit()
        return transaction_dto

    def get_by_key(self, transaction_key: str, authenticated_customer_key: str) -> dict:
        self.logger.debug(f"Buscando a transação de chave {transaction_key}")

        transaction = self.transaction_repository.get_by_key(transaction_key)

        if transaction is None:
            raise NotFoundTransaction(transaction_key)

        # Regra de segurança: o utilizador tem de pertencer à transação,
        # seja como origem, seja como destino.
        is_origin_owner = False
        if transaction.origin_account is not None:
            is_origin_owner = transaction.origin_account.customer.customer_key == authenticated_customer_key

        is_destination_owner = transaction.destination_account.customer.customer_key == authenticated_customer_key

        if not (is_origin_owner or is_destination_owner):
            raise ForbiddenAction()

        # O Controller entrega um dicionário pronto para a Rota.
        return TransactionDTO.obj_to_dict(transaction)

    def get_list(self, limit: int, offset: int, filters: dict, authenticated_customer_key: str) -> dict:
        """A página pedida, depois de conferir se o pedido faz sentido.

        Ninguém pode listar transações de conta alheia. Por isso o
        filtro por conta (origem ou destino) é obrigatório aqui, e cada
        conta filtrada precisa pertencer a quem está autenticado — do
        contrário a busca nem chega ao repositório.

        Isto é regra de negócio, não de formato: o schema
        (get_transactions.json) só confere se a chave TEM CARA de UUID.
        Se ela existe e a quem pertence é o controller quem sabe.
        """
        origin_key = filters.get("origin_account_key")
        destination_key = filters.get("destination_account_key")

        if not origin_key and not destination_key:
            raise InvalidParameter(
                "É necessário informar origin_account_key ou destination_account_key"
            )

        for account_key in filter(None, (origin_key, destination_key)):
            account = self.account_repository.get_by_key(account_key)
            if account is None or account.customer.customer_key != authenticated_customer_key:
                raise ForbiddenAction()

        transactions_list = self.transaction_repository.list_page(limit, offset, filters)

        # Pedimos um a mais que o limite só pra saber se existe próxima
        # página. Se veio o extra, ele não entra na resposta.
        is_last_page = True
        if len(transactions_list) > limit:
            is_last_page = False
            transactions_list = transactions_list[:-1]

        return {
            "transactions_list": TransactionDTO.list_obj_to_list_dict(transactions_list),
            "is_last_page": is_last_page,
        }

    def update_status(self, transaction_key: str, new_status_enumerator: str, reason: str = None) -> dict:
        """Permite que serviços internos mudem o estado (ex.: pending para confirmed)."""
        transaction = self.transaction_repository.get_by_key(transaction_key)

        if transaction is None:
            raise NotFoundTransaction(transaction_key)

        self._check_status_can_change(transaction, new_status_enumerator)

        self.transaction_repository.update_status(transaction, new_status_enumerator, reason=reason)

        transaction_dto = TransactionDTO.only_obj_key(transaction)
        self.session.commit()

        return transaction_dto

    def _check_status_can_change(self, transaction: Transaction, new_status: str) -> None:
        old_status = transaction.status.enumerator

        # Impede que uma transação já confirmada ou falhada seja reaberta.
        if old_status in [TransactionStatus.CONFIRMED, TransactionStatus.FAILED]:
            raise TransactionFinalStatus(old_status, new_status)