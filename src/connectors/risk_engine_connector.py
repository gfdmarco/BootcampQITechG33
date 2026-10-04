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

    def evaluate_transaction(self, customer_key: str, amount: int, transaction_type: str, evaluation_key: str) -> None:
        """
        Avalia a transação no Risk Engine (POST /evaluate).

        Se o motor responder DENY, lança RiskEngineDenied (403).
        Se houver falha de rede, timeout, indisponibilidade ou resposta inesperada,
        tambem nega. Para dinheiro, Risk indisponivel nao pode virar aprovacao por
        suposicao.
        """
        try:
            payload = {
                "evaluation_key": evaluation_key,
                "customer_key": customer_key,
                "amount": amount,
                "transaction_type": transaction_type,
            }
            headers = {
                "INTERNAL-TOKEN": os.getenv("RISK_INTERNAL_TOKEN", "risk_default_token")
            }
            response = requests.post(
                f"{RISK_ENGINE_URL}/evaluate",
                json=payload,
                headers=headers,
                timeout=RISK_ENGINE_TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("action") == "DENY":
                    raise RiskEngineDenied(data.get("reason", "Denied by Risk Engine Policy"))

                if data.get("action") == "APPROVE":
                    return

                raise RiskEngineDenied("Risk Engine returned an invalid decision.")

            logger.error("Risk Engine retornou status inesperado %s: %s", response.status_code, response.text)
            raise RiskEngineDenied("Risk Engine unavailable or returned an unexpected response.")

        except requests.exceptions.RequestException as e:
            logger.warning("Risk Engine indisponível ou lento: %s. Transação negada por segurança.", e)
            raise RiskEngineDenied("Risk Engine unavailable or timed out.")

    def confirm_evaluation(self, evaluation_key: str, transaction_key: str) -> None:
        """Confirma no Risk Engine que a transferência comitou no Core.

        A confirmação não participa do commit financeiro. Se falhar, o
        Risk ainda mantém a avaliação como reserved, e uma reconciliação
        futura pode resolver. O Core não desfaz dinheiro por falha nesta
        chamada pós-commit.
        """
        try:
            headers = {
                "INTERNAL-TOKEN": os.getenv("RISK_INTERNAL_TOKEN", "risk_default_token")
            }
            response = requests.post(
                f"{RISK_ENGINE_URL}/evaluate/{evaluation_key}/confirm",
                json={"transaction_key": transaction_key},
                headers=headers,
                timeout=2,
            )
            if response.status_code not in (200, 404):
                logger.warning(
                    "Risk Engine retornou %s ao confirmar avaliação %s",
                    response.status_code,
                    evaluation_key,
                )
        except requests.exceptions.RequestException as e:
            logger.warning("Falha ao confirmar avaliação de risco %s: %s", evaluation_key, e)
