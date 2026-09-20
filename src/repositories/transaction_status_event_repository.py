from models import TransactionStatusEvent

class TransactionStatusEventRepository:
    """
    Repositório responsável por registrar os eventos de mudança de status de uma transação.
    """
    def __init__(self, session):
        self.session = session

    def create_event(self, transaction_id: int, from_status_id: int, to_status_id: int, reason: str = None) -> TransactionStatusEvent:
        """
        Cria uma linha na tabela de eventos para registrar a mudança de status.
        
        Parâmetros:
        - transaction_id: ID interno da transação.
        - from_status_id: ID do status anterior (pode ser None se for a criação).
        - to_status_id: ID do novo status.
        - reason: Motivo da mudança (opcional, muito útil para status 'failed').
        """
        event = TransactionStatusEvent(
            transaction_id=transaction_id,
            from_status_id=from_status_id,
            to_status_id=to_status_id,
            reason=reason
        )
        
        self.session.add(event)

        self.session.flush()
        
        return event