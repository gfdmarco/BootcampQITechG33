from database import Context
from models import RiskProfile, RiskScoreStatus, RiskLimitPolicy


class RiskRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.get_or_create_session()

    def get_profile(self, customer_key: str) -> RiskProfile | None:
        return (
            self.session.query(RiskProfile)
            .filter(RiskProfile.customer_key == customer_key)
            .first()
        )

    def get_limit_policy(self, score_id: int, transaction_type: str) -> RiskLimitPolicy | None:
        return (
            self.session.query(RiskLimitPolicy)
            .filter(
                RiskLimitPolicy.risk_score_id == score_id,
                RiskLimitPolicy.transaction_type == transaction_type
            )
            .first()
        )

    def get_all_limit_policies(self, score_id: int) -> list[RiskLimitPolicy]:
        """Retorna TODAS as políticas de limite de um score (transfer, deposit, etc.)."""
        return (
            self.session.query(RiskLimitPolicy)
            .filter(RiskLimitPolicy.risk_score_id == score_id)
            .all()
        )

    def upsert_profile(self, customer_key: str, score_enumerator: str, reason: str) -> RiskProfile:
        """Cria ou atualiza o perfil de risco de um cliente."""
        score = (
            self.session.query(RiskScoreStatus)
            .filter(RiskScoreStatus.enumerator == score_enumerator)
            .first()
        )

        profile = self.get_profile(customer_key)
        if profile is None:
            profile = RiskProfile()
            profile.customer_key = customer_key
            self.session.add(profile)

        profile.risk_score_id = score.id
        profile.reason = reason
        return profile

    def list_all_profiles(self) -> list:
        """Retorna todos os perfis ordenados pelo mais antigo (para reavaliar primeiro)."""
        from models import RiskProfile
        return (
            self.session.query(RiskProfile)
            .order_by(RiskProfile.last_evaluated_at.asc())
            .all()
        )
