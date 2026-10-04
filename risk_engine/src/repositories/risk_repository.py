from datetime import datetime, time
from uuid import uuid4

from database import Context
from models import (
    RiskEvaluationEvent,
    RiskEvaluationRequest,
    RiskLimitConsumption,
    RiskLimitPolicy,
    RiskProfile,
    RiskScoreStatus,
)


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

    def upsert_profile(self, customer_key: str, score_enumerator: str, reason: str, evaluated_by: str = "system") -> RiskProfile:
        """Cria ou atualiza o perfil de risco de um cliente."""
        score = (
            self.session.query(RiskScoreStatus)
            .filter(RiskScoreStatus.enumerator == score_enumerator)
            .first()
        )

        profile = self.get_profile(customer_key)
        old_score_id = None
        if profile is None:
            profile = RiskProfile()
            profile.customer_key = customer_key
            self.session.add(profile)
        else:
            old_score_id = profile.risk_score_id

        profile.risk_score_id = score.id
        profile.reason = reason

        event = RiskEvaluationEvent()
        event.customer_key = customer_key
        event.from_score_id = old_score_id
        event.to_score_id = score.id
        event.reason = reason
        event.evaluated_by = evaluated_by
        self.session.add(event)

        return profile

    def list_all_profiles(self) -> list:
        """Retorna todos os perfis ordenados pelo mais antigo (para reavaliar primeiro)."""
        from models import RiskProfile
        return (
            self.session.query(RiskProfile)
            .order_by(RiskProfile.last_evaluated_at.asc())
            .all()
        )

    def get_evaluation_request(self, evaluation_key: str) -> RiskEvaluationRequest | None:
        return (
            self.session.query(RiskEvaluationRequest)
            .filter(RiskEvaluationRequest.evaluation_key == evaluation_key)
            .first()
        )

    def create_evaluation_request(
        self,
        evaluation_key: str,
        customer_key: str,
        transaction_type: str,
        amount: int,
        score: str,
        decision: str,
        reason: str | None,
    ) -> RiskEvaluationRequest:
        request = RiskEvaluationRequest()
        request.evaluation_key = evaluation_key
        request.customer_key = customer_key
        request.transaction_type = transaction_type
        request.amount = amount
        request.score = score
        request.decision = decision
        request.reason = reason
        request.status = "completed"
        self.session.add(request)
        return request

    def create_limit_consumption(
        self,
        evaluation_key: str,
        customer_key: str,
        transaction_type: str,
        amount: int,
    ) -> RiskLimitConsumption:
        consumption = RiskLimitConsumption()
        consumption.consumption_key = str(uuid4())
        consumption.evaluation_key = evaluation_key
        consumption.customer_key = customer_key
        consumption.transaction_type = transaction_type
        consumption.amount = amount
        consumption.status = "reserved"
        self.session.add(consumption)
        return consumption

    def get_daily_consumption(self, customer_key: str, transaction_type: str) -> int:
        today = datetime.utcnow().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)

        total = (
            self.session.query(RiskLimitConsumption)
            .filter(
                RiskLimitConsumption.customer_key == customer_key,
                RiskLimitConsumption.transaction_type == transaction_type,
                RiskLimitConsumption.status.in_(("reserved", "confirmed")),
                RiskLimitConsumption.requested_at >= start,
                RiskLimitConsumption.requested_at <= end,
            )
            .with_entities(RiskLimitConsumption.amount)
            .all()
        )
        return sum(row[0] for row in total)

    def confirm_consumption(self, evaluation_key: str, transaction_key: str | None = None) -> bool:
        consumption = (
            self.session.query(RiskLimitConsumption)
            .filter(RiskLimitConsumption.evaluation_key == evaluation_key)
            .first()
        )
        request = self.get_evaluation_request(evaluation_key)

        if consumption is None and request is None:
            return False

        now = datetime.utcnow()
        if consumption is not None:
            consumption.status = "confirmed"
            consumption.confirmed_at = now
            consumption.transaction_key = transaction_key

        if request is not None:
            request.status = "confirmed"
            request.transaction_key = transaction_key

        return True
