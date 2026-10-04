from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from models.base import Base
from models.risk_evaluation_request import RiskEvaluationRequest


class RiskLimitConsumption(Base):
    __tablename__ = "risk_limit_consumption"

    id = Column(Integer, primary_key=True)
    consumption_key = Column(CHAR(36), nullable=False)
    evaluation_key = Column(CHAR(36), ForeignKey(RiskEvaluationRequest.evaluation_key), nullable=False)
    customer_key = Column(CHAR(36), nullable=False)
    transaction_key = Column(CHAR(36))
    transaction_type = Column(String(30), nullable=False)
    amount = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default="reserved")
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    confirmed_at = Column(DateTime)
    canceled_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("consumption_key"),
        UniqueConstraint("evaluation_key"),
    )
