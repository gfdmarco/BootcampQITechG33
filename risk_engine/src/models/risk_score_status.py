from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from models.base import Base

class RiskScoreStatus(Base):
    __tablename__ = "risk_score_status"

    id         = Column(Integer, primary_key=True)
    enumerator = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    LOW     = "low"
    MEDIUM  = "medium"
    HIGH    = "high"
    UNKNOWN = "unknown"
