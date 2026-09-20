from models import Fee

class FeeRepository:
    def __init__(self, session):
        self.session = session

    def get_by_type(self, fee_type: str) -> Fee:
        """
        Busca uma tarifa no banco baseada no seu tipo.
        Retorna o objeto Fee ou None se não encontrar.
        """
        return self.session.query(Fee).filter(Fee.type == fee_type).first()