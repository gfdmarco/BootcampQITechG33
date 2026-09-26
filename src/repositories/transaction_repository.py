from uuid import uuid4

from database import Context
from models import Account, Transaction, TransactionStatus, TransactionStatusEvent


class TransactionRepository:
    """A camada que fala com o banco. Só aqui existe query.

    Nenhuma regra de negócio mora aqui: esta classe busca, guarda e
    atualiza — quem decide o que fazer com isso é o controller.

    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create_transaction(self, transaction_data: dict) -> Transaction:
        transaction = Transaction()

        transaction.origin_account = transaction_data.get("origin_account")
        transaction.destination_account = transaction_data.get("destination_account")
        transaction.fee = transaction_data.get("fee")

        transaction.amount = transaction_data["amount"]
        transaction.fee_amount = transaction_data.get("fee_amount", 0)
        transaction.type = transaction_data["type"]
        transaction.channel = transaction_data["channel"]

        # Geramos a chave pública segura.
        transaction.transaction_key = str(uuid4())

        # Toda transação nasce com um estado — nunca sem nenhum, igual
        # a Sample Entity nasce CREATED. PENDING aqui não gera evento
        # (não há "de onde" ela veio); o primeiro evento de verdade só
        # aparece quando `update_status` a tirar daqui.
        transaction.status = self.get_status(TransactionStatus.PENDING)

        self.session.add(transaction)
        return transaction

    def update_status(self, transaction: Transaction, new_status_enumerator: str, reason: str = None) -> None:
        """Muda o estado e deixa o rastro — as duas coisas juntas, sempre.

        Quem chama passa o NOME do novo estado (uma string, igual ao
        `update_status` da Sample Entity), nunca o objeto: é este
        método que busca o `TransactionStatus` certo, monta o evento e
        empilha em `transaction.status_events`. Ninguém fora desta
        classe precisa saber que essa tabela satélite existe.
        """
        old_status = transaction.status
        new_status = self.get_status(new_status_enumerator)

        transaction.status = new_status

        new_status_event = TransactionStatusEvent()
        new_status_event.from_status = old_status
        new_status_event.to_status = new_status
        new_status_event.reason = reason

        transaction.status_events.append(new_status_event)

    def get_status(self, enumerator: str) -> TransactionStatus:
        return self.session.query(TransactionStatus).filter(TransactionStatus.enumerator == enumerator).one()

    def get_by_key(self, transaction_key: str) -> Transaction:
        return self.session.query(Transaction).filter(Transaction.transaction_key == transaction_key).first()

    def get_by_origin_account_key(self, origin_account_key: str) -> list:
        """Busca todas as transações enviadas por uma conta específica (usando a chave segura)."""
        return self.session.query(Transaction).join(
            Transaction.origin_account
        ).filter(Account.account_key == origin_account_key).all()

    def get_by_destination_account_key(self, destination_account_key: str) -> list:
        """Busca todas as transações recebidas por uma conta específica (usando a chave segura)."""
        return self.session.query(Transaction).join(
            Transaction.destination_account
        ).filter(Account.account_key == destination_account_key).all()

    def get_by_fee_id(self, fee_id: int) -> list:
        """Busca transações por uma tarifa interna específica.

        Único método desta classe que ainda recebe um `id` cru — de
        propósito, deliberadamente marcado assim. Ele existe para uso
        INTERNO (relatório, job, outro repository), nunca chamado a
        partir de um controller com dado vindo de fora. Se um dia
        precisar disso a partir de uma chave pública, é sinal de que
        `Fee` também precisa de uma `fee_key`, e este método vira
        `get_by_fee_key`.
        """
        return self.session.query(Transaction).filter(Transaction.fee_id == fee_id).all()

    def get_by_type(self, transaction_type: str) -> list:
        """Busca todas as transações de um tipo específico (ex.: 'deposit' ou 'transfer')."""
        return self.session.query(Transaction).filter(Transaction.type == transaction_type).all()

    def get_by_channel(self, channel: str) -> list:
        """Busca todas as transações processadas por um canal específico (ex.: 'pix', 'ted')."""
        return self.session.query(Transaction).filter(Transaction.channel == channel).all()

    def list_page(self, limit: int, offset: int, filters: dict) -> list:
        """A página, estreitada por quantos filtros vierem preenchidos.

        Todo filtro segue a mesma forma do `list_page` da Sample
        Entity: veio vazio, não entra na query; veio preenchido, vira
        mais um `.filter()` — e como todos caem na mesma query, eles se
        somam com E.

        O desempate por `id` no fim existe pelo mesmo motivo de lá:
        duas transações podem nascer no mesmo instante, e sem um
        segundo critério a página 2 ganha permissão de repetir ou
        engolir uma linha.
        """
        query = self.session.query(Transaction)

        origin_account_key = filters.get("origin_account_key")
        if origin_account_key is not None:
            query = query.join(Transaction.origin_account).filter(Account.account_key == origin_account_key)

        destination_account_key = filters.get("destination_account_key")
        if destination_account_key is not None:
            query = query.join(Transaction.destination_account).filter(
                Account.account_key == destination_account_key
            )

        transaction_type = filters.get("type")
        if transaction_type is not None:
            query = query.filter(Transaction.type == transaction_type)

        channel = filters.get("channel")
        if channel is not None:
            query = query.filter(Transaction.channel == channel)

        query = query.order_by(Transaction.created_at.desc(), Transaction.id.desc())

        return query.limit(limit + 1).offset(offset).all()