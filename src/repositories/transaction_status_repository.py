from models import TransactionStatus

class TransactionStatusRepository:
    def __init__(self, session):
        self.session = session

    def get_by_enumerator(self, enumerator: str) -> TransactionStatus:
        """
        Busca o status pelo nome (ex: 'pending').
        """
        return self.session.query(TransactionStatus).filter(
            TransactionStatus.enumerator == enumerator
        ).first()