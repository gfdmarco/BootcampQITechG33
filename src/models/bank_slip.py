from sqlalchemy import CHAR, Column, DateTime, Date, ForeignKey, Integer, String, BigInteger, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import BankSlipStatus, Transaction, Account


class BankSlip(Base):
    __tablename__ = "bank_slip"

    id = Column(Integer, primary_key=True)
    bank_slip_key = Column(CHAR(36), nullable=False)
    amount = Column(BigInteger, nullable=False)
    expiration_date = Column(Date, nullable=False)
    external_key = Column(CHAR(36), nullable=True)
    barcode = Column(CHAR(47), nullable=True)
    transaction_id = Column(Integer, ForeignKey(Transaction.id))
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    status_id = Column(Integer, ForeignKey(BankSlipStatus.id), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("bank_slip_key"),
        UniqueConstraint("external_key"),
        UniqueConstraint("transaction_id"),
        CheckConstraint("amount > 0"),
    )
    
    transaction = relationship("Transaction", foreign_keys=[transaction_id], lazy="selectin")
    account = relationship("Account", foreign_keys=[account_id], lazy="selectin")
    status = relationship("BankSlipStatus", foreign_keys=[status_id], lazy="selectin")
    status_events = relationship(
        "BankSlipStatusEvent", back_populates="bank_slip",
        order_by="asc(BankSlipStatusEvent.created_at)",
    )