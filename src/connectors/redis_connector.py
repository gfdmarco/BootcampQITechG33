import os
import redis
import logging

logger = logging.getLogger(__name__)

# Conexão única e reutilizável (pool de conexões embutido na lib)
_client: redis.Redis | None = None

def get_redis() -> redis.Redis:
    """
    Retorna o cliente Redis compartilhado.
    Usa connection pool por padrão — thread-safe e eficiente.
    """
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _client = redis.from_url(url, decode_responses=True)
    return _client


class RedisCacheConnector:
    """
    Wrapper de alto nível para operações de cache no projeto.
    Cada chamada tem tratativa de falha embutida: se o Redis cair,
    retorna None/False sem derrubar a aplicação (Fail-Open).
    """

    def __init__(self):
        self.client = get_redis()

    def get(self, key: str) -> str | None:
        try:
            return self.client.get(key)
        except redis.RedisError as e:
            logger.warning(f"Redis GET falhou para '{key}': {e}")
            return None

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        try:
            self.client.set(key, value, ex=ttl_seconds)
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis SET falhou para '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            self.client.delete(key)
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis DELETE falhou para '{key}': {e}")
            return False

    def incr(self, key: str, ttl_seconds: int = 60) -> int | None:
        """Incremento atômico — usado para Rate Limiting."""
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            result = pipe.execute()
            return result[0]
        except redis.RedisError as e:
            logger.warning(f"Redis INCR falhou para '{key}': {e}")
            return None
