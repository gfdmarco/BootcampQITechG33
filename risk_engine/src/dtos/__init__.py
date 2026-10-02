from models import RiskProfile

class RiskProfileDTO:
    @staticmethod
    def to_dict(profile: RiskProfile) -> dict:
        return {
            "customer_key":      profile.customer_key,
            "score":             profile.risk_score.enumerator,
            "reason":            profile.reason,
            "last_evaluated_at": profile.last_evaluated_at.isoformat(),
        }

class EvaluationDTO:
    @staticmethod
    def approved(score: str) -> dict:
        return {"action": "APPROVE", "score": score}

    @staticmethod
    def denied(score: str, reason: str) -> dict:
        return {"action": "DENY", "score": score, "reason": reason}
