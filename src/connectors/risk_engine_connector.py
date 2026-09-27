import requests
import os
import logging
from errors import RiskEngineDenied

class RiskEngineConnector:
    def __init__(self):
        self.risk_url = os.getenv("RISK_ENGINE_URL", "http://risk_engine:3000")
        self.logger = logging.getLogger(__name__)

    def evaluate_transaction(self, customer_key: str, amount: int, transaction_type: str) -> None:
        """
        Consulta o motor de risco de forma síncrona.
        Levanta RiskEngineDenied se a transação for bloqueada.
        Engole a exceção e permite seguir (Fail-Open) se o serviço estiver fora.
        """
        try:
            payload = {
                "customer_key": customer_key,
                "amount": amount,
                "transaction_type": transaction_type
            }
            # Timeout curto de 2s para não derrubar a API principal
            response = requests.post(f"{self.risk_url}/evaluate", json=payload, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("action") == "DENY":
                    raise RiskEngineDenied(data.get("reason", "Unknown Risk"))
                    
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Risk Engine Connector indisponível ou lento: {e}. Transação prosseguindo por resiliência (Fail-Open).")
