from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, BigInteger, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import AccountStatus, Customer


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False)
    customer_id = Column(Integer, ForeignKey(Customer.id), nullable=False)
    branch = Column(String(10), nullable=False)
    number = Column(String(20), nullable=False)
    type = Column(String(20), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    status_id = Column(Integer, ForeignKey(AccountStatus.id), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("account_key"),
        UniqueConstraint("branch", "number"),
        CheckConstraint("balance >= 0"),
    )

    customer = relationship("Customer", foreign_keys=[customer_id], lazy="selectin")
    status = relationship("AccountStatus", foreign_keys=[status_id], lazy="selectin")