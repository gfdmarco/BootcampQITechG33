from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from models.base import Base


class BankSlipStatus(Base):
    __tablename__ = "bank_slip_status"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("enumerator"),)

    PENDING = "pending"
    ISSUED = "issued"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"