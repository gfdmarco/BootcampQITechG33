from uuid import uuid4
from models import Transaction

class TransactionRepository:
    """
    Repositório central para salvar apenas os dados da tabela de transações.
    """
    def __init__(self, session):
        self.session = session

    def create_transaction(self, transaction_data: dict) -> Transaction:
        """
        Cria uma nova transação no banco de dados.
        """
        transaction = Transaction(**transaction_data)

        transaction.transaction_key = str(uuid4())
        
        self.session.add(transaction)
        self.session.flush() 
        
        return transaction