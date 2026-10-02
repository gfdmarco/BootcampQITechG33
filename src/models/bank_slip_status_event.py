from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import BankSlip, BankSlipStatus


class BankSlipStatusEvent(Base):
    __tablename__ = "bank_slip_status_event"

    id = Column(Integer, primary_key=True)
    bank_slip_id = Column(Integer, ForeignKey(BankSlip.id), nullable=False)
    from_status_id = Column(Integer, ForeignKey(BankSlipStatus.id), nullable=True)
    to_status_id = Column(Integer, ForeignKey(BankSlipStatus.id), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    bank_slip = relationship("BankSlip", foreign_keys=[bank_slip_id], back_populates="status_events", lazy="selectin")
    from_status = relationship("BankSlipStatus", foreign_keys=[from_status_id], lazy="selectin")
    to_status = relationship("BankSlipStatus", foreign_keys=[to_status_id], lazy="selectin")