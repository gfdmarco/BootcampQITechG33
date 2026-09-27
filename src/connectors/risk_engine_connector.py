import requests
import os
import logging
from connectors.redis_connector import RedisCacheConnector
from errors import RiskEngineDenied

RISK_SCORE_TTL = 6 * 60 * 60  # 6 horas — ciclo do LLM Worker

class RiskEngineConnector:
    def __init__(self):
        self.risk_url = os.getenv("RISK_ENGINE_URL", "http://risk_engine:3000")
        self.logger = logging.getLogger(__name__)
        self.cache = RedisCacheConnector()

    def evaluate_transaction(self, customer_key: str, amount: int, transaction_type: str) -> None:
        """
        Consulta o score de risco do cliente.

        Estratégia em duas camadas:
          1. Lê o score pré-calculado do Redis (< 1ms). Se existir e for HIGH, bloqueia.
          2. Se o Redis não tiver o score (cold start ou TTL expirado), cai no
             HTTP ao Risk Engine como fallback síncrono.
        Engole falhas de rede (Fail-Open) para não derrubar o Core.
        """
        cache_key = f"risk:{customer_key}"

        # Camada 1: Redis (Read Model — path quente)
        cached_score = self.cache.get(cache_key)
        if cached_score is not None:
            self.logger.debug(f"Risk score lido do cache para {customer_key}: {cached_score}")
            if cached_score == "high":
                raise RiskEngineDenied("HIGH_RISK_SCORE_CACHED")
            return  # low ou medium — aprovado direto

        # Camada 2: HTTP ao Risk Engine (fallback — cold start)
        try:
            payload = {
                "customer_key": customer_key,
                "amount": amount,
                "transaction_type": transaction_type
            }
            response = requests.post(f"{self.risk_url}/evaluate", json=payload, timeout=2)

            if response.status_code == 200:
                data = response.json()
                # Persiste no Redis para as próximas chamadas
                score = data.get("score", "unknown")
                self.cache.set(cache_key, score, ttl_seconds=RISK_SCORE_TTL)

                if data.get("action") == "DENY":
                    raise RiskEngineDenied(data.get("reason", "Unknown Risk"))

        except requests.exceptions.RequestException as e:
            self.logger.warning(
                f"Risk Engine Connector indisponível ou lento: {e}. "
                "Transação prosseguindo por resiliência (Fail-Open)."
            )
