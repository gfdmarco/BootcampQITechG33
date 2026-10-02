from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.account import Account

class CorporateAccount(Base):
    __tablename__ = "corporate_account"

    id = Column(Integer, primary_key=True)
    corporate_id = Column(Integer, ForeignKey("corporate_customer.id"), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("corporate_id", "account_id"),
    )

    corporate = relationship("CorporateCustomer", back_populates="accounts", lazy="selectin")
    account = relationship("Account", lazy="selectin")
