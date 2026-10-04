from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from models.base import Base
from models.risk_score_status import RiskScoreStatus


class RiskEvaluationEvent(Base):
    __tablename__ = "risk_evaluation_event"

    id = Column(Integer, primary_key=True)
    customer_key = Column(CHAR(36), nullable=False)
    from_score_id = Column(Integer, ForeignKey(RiskScoreStatus.id), nullable=True)
    to_score_id = Column(Integer, ForeignKey(RiskScoreStatus.id), nullable=False)
    reason = Column(Text)
    evaluated_by = Column(String(50), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    from_score = relationship("RiskScoreStatus", foreign_keys=[from_score_id])
    to_score = relationship("RiskScoreStatus", foreign_keys=[to_score_id])
