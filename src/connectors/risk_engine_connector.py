from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import RISK_ENGINE_URL, RISK_INTERNAL_TOKEN, RISK_ENGINE_TIMEOUT
import logging

logger = logging.getLogger(__name__)

class RiskEngineConnector(RestConnector):
    """
    Fala com a API do Motor de Risco.
    
    Consulta o perfil de risco de um cliente passando a customer_key.
    Retorna o score (low, medium, high, ou unknown em caso de falha).
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
