from database import Context
from dtos import EvaluationDTO, RiskProfileDTO
from errors import TransactionDeniedByRisk, ProfileNotFound, InvalidScoreValue
from models import RiskScoreStatus
from repositories import RiskRepository


VALID_SCORES = {RiskScoreStatus.LOW, RiskScoreStatus.MEDIUM, RiskScoreStatus.HIGH, RiskScoreStatus.UNKNOWN}


class RiskController:
    def __init__(self, context: Context) -> None:
        self.context    = context
        self.repository = RiskRepository(context)

    def evaluate(self, customer_key: str, amount: int, transaction_type: str) -> dict:
        """
        Avalia se uma transação deve ser aprovada ou negada.
        Consulta o perfil de risco do cliente e a política de limites correspondente.
        Clientes sem perfil recebem tratamento UNKNOWN (política padrão).
        """
        profile = self.repository.get_profile(customer_key)

        if profile is None:
            score_enumerator = RiskScoreStatus.UNKNOWN
            score_status = (
                self.repository.session.query(RiskScoreStatus)
                .filter(RiskScoreStatus.enumerator == score_enumerator)
                .first()
            )
            score_id = score_status.id
        else:
            score_enumerator = profile.risk_score.enumerator
            score_id         = profile.risk_score_id

        policy = self.repository.get_limit_policy(score_id, transaction_type)

        if policy and amount > policy.max_amount_per_tx:
            reason = f"LIMIT_EXCEEDED: amount {amount} exceeds max {policy.max_amount_per_tx} for score {score_enumerator}"
            return EvaluationDTO.denied(score_enumerator, reason)

        return EvaluationDTO.approved(score_enumerator)

    def update_profile(self, customer_key: str, score: str, reason: str) -> dict:
        """
        Atualiza o perfil de risco de um cliente.
        Chamado exclusivamente pelo LLM Worker via PATCH /risk_profile/{key}.
        """
        if score not in VALID_SCORES:
            raise InvalidScoreValue(score)

        profile = self.repository.upsert_profile(customer_key, score, reason)
        return RiskProfileDTO.to_dict(profile)

    def get_profile(self, customer_key: str) -> dict:
        """Retorna o perfil de risco atual de um cliente para auditoria."""
        profile = self.repository.get_profile(customer_key)
        if profile is None:
            raise ProfileNotFound(customer_key)
        return RiskProfileDTO.to_dict(profile)
