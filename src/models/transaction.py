from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, BigInteger, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, Fee, TransactionStatus


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False)
    origin_account_id = Column(Integer, ForeignKey(Account.id), nullable=True)       # NULL para depósito
    destination_account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    amount = Column(BigInteger, nullable=False)
    fee_amount = Column(BigInteger, nullable=False, default=0)
    fee_id = Column(Integer, ForeignKey(Fee.id), nullable=True)
    type = Column(String(20), nullable=False)      # deposit / transfer
    channel = Column(String(50), nullable=False)    # pix / ted / card / international
    status_id = Column(Integer, ForeignKey(TransactionStatus.id), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("transaction_key"),
        CheckConstraint("type <> 'transfer' OR origin_account_id IS NOT NULL"),
    )

    origin_account = relationship("Account", foreign_keys=[origin_account_id], lazy="selectin")
    destination_account = relationship("Account", foreign_keys=[destination_account_id], lazy="selectin")
    fee = relationship("Fee", foreign_keys=[fee_id], lazy="selectin")
    status = relationship("TransactionStatus", foreign_keys=[status_id], lazy="selectin")
    status_events = relationship(
        "TransactionStatusEvent", back_populates="Transaction",
        order_by="asc(TransactionStatusEvent.created_at)",
    )