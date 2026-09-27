import os
import json
import redis
import logging

logger = logging.getLogger(__name__)

# Conexão única e reutilizável (pool de conexões embutido na lib)
_client: redis.Redis | None = None

RISK_CACHE_TTL = 6 * 60 * 60  # 6h — alinhado ao ciclo do LLM Worker


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _client = redis.from_url(url, decode_responses=True)
    return _client


class RedisCacheConnector:
    """
    Cache de avaliação de risco dentro do Motor de Risco.

    Armazena o resultado completo da avaliação (score + limites por tipo
    de transação) como JSON, indexado por customer_key. Isso elimina
    queries ao Postgres para clientes já classificados pelo LLM Worker.

    Estratégia Fail-Open: se o Redis cair, o Controller segue para o
    banco normalmente — sem derrubar a aplicação.
    """

    def __init__(self):
        self.client = _get_client()

    def get_evaluation_cache(self, customer_key: str) -> dict | None:
        """Lê o cache de avaliação de um cliente. Retorna None se miss."""
        try:
            raw = self.client.get(f"risk:eval:{customer_key}")
            if raw is not None:
                return json.loads(raw)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Redis GET falhou para 'risk:eval:{customer_key}': {e}")
        return None

    def set_evaluation_cache(self, customer_key: str, data: dict) -> None:
        """Grava o cache de avaliação de um cliente com TTL."""
        try:
            self.client.set(
                f"risk:eval:{customer_key}",
                json.dumps(data),
                ex=RISK_CACHE_TTL
            )
        except redis.RedisError as e:
            logger.warning(f"Redis SET falhou para 'risk:eval:{customer_key}': {e}")

    def invalidate(self, customer_key: str) -> None:
        """Invalida o cache quando o LLM Worker atualiza o perfil."""
        try:
            self.client.delete(f"risk:eval:{customer_key}")
        except redis.RedisError as e:
            logger.warning(f"Redis DELETE falhou para 'risk:eval:{customer_key}': {e}")
