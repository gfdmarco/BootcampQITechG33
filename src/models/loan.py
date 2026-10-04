from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, BigInteger, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.account import Account

class Loan(Base):
    __tablename__ = "loan"

    id = Column(Integer, primary_key=True)
    loan_key = Column(CHAR(36), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    requested_amount = Column(BigInteger, nullable=False)
    total_amount_due = Column(BigInteger, nullable=False)
    interest_rate = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    idempotency_key = Column(String(120), nullable=True)   # header Idempotency-Key do POST /loans

    __table_args__ = (
        UniqueConstraint("loan_key"),
        UniqueConstraint("idempotency_key"),
    )

    account = relationship("Account", foreign_keys=[account_id], lazy="selectin")
    installments = relationship("LoanInstallment", back_populates="loan", order_by="asc(LoanInstallment.installment_number)")
