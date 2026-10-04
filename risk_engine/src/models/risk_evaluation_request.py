from sqlalchemy import BigInteger, CHAR, Column, DateTime, Integer, String, Text, UniqueConstraint, func

from models.base import Base


class RiskEvaluationRequest(Base):
    __tablename__ = "risk_evaluation_request"

    id = Column(Integer, primary_key=True)
    evaluation_key = Column(CHAR(36), nullable=False)
    customer_key = Column(CHAR(36), nullable=False)
    transaction_type = Column(String(30), nullable=False)
    amount = Column(BigInteger, nullable=False)
    score = Column(String(20), nullable=False)
    decision = Column(String(20), nullable=False)
    reason = Column(Text)
    status = Column(String(20), nullable=False, default="completed")
    transaction_key = Column(CHAR(36))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("evaluation_key"),)
