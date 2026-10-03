import logging
import os

import requests

from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import RISK_ENGINE_URL, RISK_INTERNAL_TOKEN, RISK_ENGINE_TIMEOUT
from errors import RiskEngineDenied

logger = logging.getLogger(__name__)


class RiskEngineConnector(RestConnector):
    """
    Fala com a API do Motor de Risco.

    - get_customer_risk_score: consulta o score do cliente (usado pelo empréstimo).
    - evaluate_transaction: avalia uma transação contra os limites do score
      (usado pela transferência).
    """

    def __init__(self) -> None:
        super().__init__(
            class_name=__name__,
            base_url=RISK_ENGINE_URL,
            timeout=RISK_ENGINE_TIMEOUT,
            internal_token=RISK_INTERNAL_TOKEN,
        )

    def get_customer_risk_score(self, customer_key: str) -> str:
        """
        Busca o score de risco do cliente.
        Se ocorrer um erro de conexão, timeout, ou a API não responder com sucesso (2xx),
        fallback para "unknown".
        """
        try:
            response = self.send(endpoint=f"/risk_profile/{customer_key}", method="GET")

            if response.status == 200 and response.json:
                return response.json.get("score", "unknown")

            logger.warning(f"Risco não pôde ser calculado para {customer_key}. Fallback para 'unknown'.")
            return "unknown"

        except Exception as e:
            logger.error(f"Erro ao consultar Risk Engine para {customer_key}: {e}. Fallback para 'unknown'.")
            return "unknown"

    def evaluate_transaction(self, customer_key: str, amount: int, transaction_type: str) -> None:
        """
        Avalia a transação no Risk Engine (POST /evaluate).

        Se o motor responder DENY, lança RiskEngineDenied (403).
        Se houver falha de rede (timeout/indisponibilidade/403 do token), entra em
        Degraded Mode: transações acima de R$ 1000 são bloqueadas por segurança.
        """
        try:
            payload = {
                "customer_key": customer_key,
                "amount": amount,
                "transaction_type": transaction_type,
            }
            headers = {
                "INTERNAL-TOKEN": os.getenv("RISK_INTERNAL_TOKEN", "risk_default_token")
            }
            response = requests.post(f"{RISK_ENGINE_URL}/evaluate", json=payload, headers=headers, timeout=2)

            if response.status_code == 200:
                data = response.json()
                if data.get("action") == "DENY":
                    raise RiskEngineDenied(data.get("reason", "Denied by Risk Engine Policy"))
            elif response.status_code == 403:
                logger.error("Risk Engine retornou 403 Forbidden. Verifique o RISK_INTERNAL_TOKEN.")
                # Falha de autenticação com o motor: trata como indisponibilidade (Degraded Mode)
                raise requests.exceptions.RequestException("Risk Engine Authentication Failed")

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Risk Engine indisponível ou lento: {e}. "
                "Transação prosseguindo em Degraded Mode (limite de R$ 1000)."
            )
            # Em vez de liberar qualquer valor (Fail-Open), aplica um limite restrito.
            DEGRADED_MODE_LIMIT = 100000  # R$ 1000 em centavos
            if amount > DEGRADED_MODE_LIMIT:
                raise RiskEngineDenied("Transação negada pois excede o limite restrito do modo de segurança.")