import os
import logging

from connectors import RedisCacheConnector
from database import Context
from dtos import EvaluationDTO, RiskProfileDTO
from errors import TransactionDeniedByRisk, ProfileNotFound, InvalidScoreValue
from models import RiskScoreStatus
from repositories import RiskRepository

logger = logging.getLogger(__name__)

VALID_SCORES = {RiskScoreStatus.LOW, RiskScoreStatus.MEDIUM, RiskScoreStatus.HIGH, RiskScoreStatus.UNKNOWN}


class RiskController:
    def __init__(self, context: Context) -> None:
        self.context    = context
        self.repository = RiskRepository(context)
        self.cache      = RedisCacheConnector()

    # ── Avaliação de Transação ──────────────────────────────────────────

    def evaluate(self, customer_key: str, amount: int, transaction_type: str) -> dict:
        """
        Avalia se uma transação deve ser aprovada ou negada.

        Estratégia em duas camadas:
          1. Redis (< 1ms): lê score + limites pré-cacheados do cliente.
          2. Postgres (fallback): se o cache estiver vazio, consulta o
             banco, responde e popula o cache para as próximas chamadas.

        Clientes sem perfil recebem tratamento UNKNOWN (política padrão).
        """
        # ── Camada 1: Cache Redis ──
        cached = self.cache.get_evaluation_cache(customer_key)
        if cached is not None:
            logger.debug(f"Cache HIT para {customer_key}")
            return self._decide(cached, amount, transaction_type, customer_key)

        # ── Camada 2: Banco de Dados (fallback) ──
        logger.debug(f"Cache MISS para {customer_key}, consultando Postgres")
        eval_data = self._build_evaluation_data(customer_key)

        # Popula o cache para as próximas chamadas
        self.cache.set_evaluation_cache(customer_key, eval_data)

        return self._decide(eval_data, amount, transaction_type, customer_key)

    def _build_evaluation_data(self, customer_key: str) -> dict:
        """
        Monta o dicionário de avaliação a partir do banco.
        Contém score e todos os limites por tipo de transação.
        """
        profile = self.repository.get_profile(customer_key)

        if profile is None:
            # Cria o perfil inicial como UNKNOWN para o cliente, assim
            # o LLM Worker conseguirá descobri-lo nas próximas execuções.
            profile = self.repository.upsert_profile(customer_key, RiskScoreStatus.UNKNOWN, "Perfil inicial criado via evaluate")
            self.context.db_session.commit()
            self.context.db_session.refresh(profile)

        score_enumerator = profile.risk_score.enumerator
        score_id         = profile.risk_score_id

        # Carrega TODOS os limites desse score de uma vez (pix, ted, card...)
        policies = self.repository.get_all_limit_policies(score_id)
        limits = {
            p.transaction_type: {
                "max_amount_per_tx": p.max_amount_per_tx,
                "max_amount_daily":  p.max_amount_daily,
            }
            for p in policies
        }

        return {"score": score_enumerator, "limits": limits}

    def _decide(self, eval_data: dict, amount: int, transaction_type: str, customer_key: str) -> dict:
        """Aplica a política de limites sobre os dados de avaliação."""
        score  = eval_data["score"]
        limits = eval_data.get("limits", {})
        policy = limits.get(transaction_type)

        if policy:
            if amount > policy["max_amount_per_tx"]:
                reason = (
                    f"LIMIT_EXCEEDED: amount {amount} exceeds max per tx "
                    f"{policy['max_amount_per_tx']} for score {score}"
                )
                return EvaluationDTO.denied(score, reason)

            daily_spend = self.cache.get_daily_spend(customer_key, transaction_type)
            if amount + daily_spend > policy["max_amount_daily"]:
                reason = (
                    f"DAILY_LIMIT_EXCEEDED: amount {amount} + daily spend {daily_spend} "
                    f"exceeds max daily {policy['max_amount_daily']} for score {score}"
                )
                return EvaluationDTO.denied(score, reason)
                
            # Increments optimistic daily spend (we assume it succeeds)
            self.cache.increment_daily_spend(customer_key, transaction_type, amount)

        return EvaluationDTO.approved(score)

    # ── Atualização de Perfil (LLM Worker) ──────────────────────────────

    def update_profile(self, customer_key: str, score: str, reason: str) -> dict:
        """
        Atualiza o perfil de risco de um cliente.
        Chamado exclusivamente pelo LLM Worker via PATCH /risk_profile/{key}.
        Invalida o cache Redis para que a próxima avaliação reflita o novo score.
        """
        if score not in VALID_SCORES:
            raise InvalidScoreValue(score)

        profile = self.repository.upsert_profile(customer_key, score, reason)

        self.context.db_session.commit()
        self.context.db_session.refresh(profile)

        # Invalida o cache — a próxima chamada ao evaluate reconstrói com o score novo
        self.cache.invalidate(customer_key)

        return RiskProfileDTO.to_dict(profile)

    # ── Consultas ───────────────────────────────────────────────────────

    def get_profile(self, customer_key: str) -> dict:
        """Retorna o perfil de risco atual de um cliente para auditoria."""
        profile = self.repository.get_profile(customer_key)
        if profile is None:
            raise ProfileNotFound(customer_key)
        return RiskProfileDTO.to_dict(profile)

    def list_profiles(self) -> list[dict]:
        """Lista todos os perfis para o LLM Worker descobrir quais clientes avaliar."""
        from dtos import RiskProfileDTO
        profiles = self.repository.list_all_profiles()
        return [RiskProfileDTO.to_dict(p) for p in profiles]
