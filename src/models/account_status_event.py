from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Account, AccountStatus


class AccountStatusEvent(Base):
    __tablename__ = "account_status_event"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    from_status_id = Column(Integer, ForeignKey(AccountStatus.id), nullable=True)
    to_status_id = Column(Integer, ForeignKey(AccountStatus.id), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    account = relationship("Account", foreign_keys=[account_id], lazy="selectin")
    from_status = relationship("AccountStatus", foreign_keys=[from_status_id], lazy="selectin")
    to_status = relationship("AccountStatus", foreign_keys=[to_status_id], lazy="selectin")