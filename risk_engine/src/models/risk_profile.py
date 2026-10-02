from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base

class RiskProfile(Base):
    __tablename__ = "risk_profile"

    id                = Column(Integer, primary_key=True)
    customer_key      = Column(String(36), nullable=False)
    risk_score_id     = Column(Integer, ForeignKey("risk_score_status.id"), nullable=False)
    reason            = Column(Text)
    last_evaluated_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at        = Column(DateTime, nullable=False, server_default=func.now())
    updated_at        = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    risk_score = relationship("RiskScoreStatus", foreign_keys=[risk_score_id])

    __table_args__ = (UniqueConstraint("customer_key"),)
