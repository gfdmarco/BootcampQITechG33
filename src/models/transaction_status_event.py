from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Transaction, TransactionStatus


class TransactionStatusEvent(Base):
    __tablename__ = "transaction_status_event"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey(Transaction.id), nullable=False)
    from_status_id = Column(Integer, ForeignKey(TransactionStatus.id), nullable=True)
    to_status_id = Column(Integer, ForeignKey(TransactionStatus.id), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    transaction = relationship("Transaction", foreign_keys=[transaction_id], lazy="selectin")
    from_status = relationship("TransactionStatus", foreign_keys=[from_status_id], lazy="selectin")
    to_status = relationship("TransactionStatus", foreign_keys=[to_status_id], lazy="selectin")