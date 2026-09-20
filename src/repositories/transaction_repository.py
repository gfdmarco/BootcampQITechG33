from uuid import uuid4
from database import Context
from models import Transaction, Account

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
        transaction.status = transaction_data.get("status")
        
        transaction.amount = transaction_data["amount"]
        transaction.fee_amount = transaction_data.get("fee_amount", 0)
        transaction.type = transaction_data["type"]
        transaction.channel = transaction_data["channel"]
        
        # Geramos a chave pública segura
        transaction.transaction_key = str(uuid4())
        
        self.session.add(transaction)
        return transaction

    def update_status(self, transaction: Transaction, new_status, reason: str = None) -> None:
        """
        Atualiza o estado da transação e regista automaticamente o evento histórico.
        
        Parâmetros:
        - transaction: O objeto da transação atual.
        - new_status: O objeto TransactionStatus que representa o novo estado.
        - reason: Uma justificação em texto (opcional, útil para quando o estado é 'failed').
        """

        old_status = transaction.status
        

        transaction.status = new_status
        from models import TransactionStatusEvent 
        
        new_event = TransactionStatusEvent()
        new_event.from_status = old_status
        new_event.to_status = new_status
        new_event.reason = reason
        transaction.status_events.append(new_event)

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
        """Busca todas as transações que utilizaram uma tarifa interna específica."""
        return self.session.query(Transaction).filter(Transaction.fee_id == fee_id).all()

    def get_by_type(self, transaction_type: str) -> list:
        """Busca todas as transações de um tipo específico (ex: 'deposit' ou 'transfer')."""
        return self.session.query(Transaction).filter(Transaction.type == transaction_type).all()

    def get_by_channel(self, channel: str) -> list:
        """Busca todas as transações processadas por um canal específico (ex: 'pix', 'ted')."""
        return self.session.query(Transaction).filter(Transaction.channel == channel).all()

    def list_page(self, limit: int, offset: int, filters: dict) -> list:
        """A pagina, estreitada por quantos filtros vierem preenchidos.
        Todo filtro segue a mesma forma: veio vazio, nao entra na query;
        veio preenchido, vira mais um `.filter()`.
        """
        query = self.session.query(Transaction)

        origin_account_key = filters.get("origin_account_key")
        if origin_account_key is not None:
            query = query.join(Transaction.origin_account).filter(Account.account_key == origin_account_key)

        destination_account_key = filters.get("destination_account_key")
        if destination_account_key is not None:
            query = query.join(Transaction.destination_account).filter(Account.account_key == destination_account_key)

        transaction_type = filters.get("type")
        if transaction_type is not None:
            query = query.filter(Transaction.type == transaction_type)
            
        channel = filters.get("channel")
        if channel is not None:
            query = query.filter(Transaction.channel == channel)
    
        query = query.order_by(Transaction.created_at.desc())

        return query.limit(limit + 1).offset(offset).all()