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
        Consulta o score de risco do cliente.

        Chama o Risk Engine sincronicamente para avaliar a transação contra
        a política de limites do score do cliente (ex: HIGH = R$1k).
        Se houver falha de rede (timeout/indisponibilidade), entra em Degraded
        Mode: transações acima de R$1000 são bloqueadas por segurança.
        """
        try:
            payload = {
                "customer_key": customer_key,
                "amount": amount,
                "transaction_type": transaction_type
            }
            response = requests.post(f"{self.risk_url}/evaluate", json=payload, timeout=2)

            if response.status_code == 200:
                data = response.json()
                if data.get("action") == "DENY":
                    raise RiskEngineDenied(data.get("reason", "Denied by Risk Engine Policy"))

        except requests.exceptions.RequestException as e:
            self.logger.warning(
                f"Risk Engine Connector indisponível ou lento: {e}. "
                "Transação prosseguindo em Degraded Mode (limite de R$ 1000)."
            )
            # Em vez de liberar qualquer valor (Fail-Open), aplicamos um
            # limite restrito de fallback.
            DEGRADED_MODE_LIMIT = 100000 # R$ 1000 em centavos
            if amount > DEGRADED_MODE_LIMIT:
                raise RiskEngineDenied("Transação negada pois excede o limite restrito do modo de segurança.")
