from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base

class RiskLimitPolicy(Base):
    __tablename__ = "risk_limit_policy"

    id                  = Column(Integer, primary_key=True)
    risk_score_id       = Column(Integer, ForeignKey("risk_score_status.id"), nullable=False)
    transaction_type    = Column(String(30), nullable=False)
    max_amount_per_tx   = Column(BigInteger, nullable=False)
    max_amount_daily    = Column(BigInteger, nullable=False)
    created_at          = Column(DateTime, nullable=False, server_default=func.now())

    risk_score = relationship("RiskScoreStatus", foreign_keys=[risk_score_id])

    __table_args__ = (UniqueConstraint("risk_score_id", "transaction_type"),)
