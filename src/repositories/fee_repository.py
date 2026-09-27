from database import Context
from models import Fee

class FeeRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_type(self, fee_type: str) -> Fee:
        """
        Busca uma tarifa no banco baseada no seu tipo.
        Retorna o objeto Fee ou None se não encontrar.
        """
        return self.session.query(Fee).filter(Fee.type == fee_type).first()