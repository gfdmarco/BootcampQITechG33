from sqlalchemy import CHAR, BigInteger, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.account import Account
from models.customer import Customer

class CorporateTransferRequest(Base):
    __tablename__ = "corporate_transfer_request"

    id = Column(Integer, primary_key=True)
    corporate_id = Column(Integer, ForeignKey("corporate_customer.id"), nullable=False)
    requester_customer_id = Column(Integer, ForeignKey(Customer.id), nullable=False)
    origin_account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    destination_account_key = Column(CHAR(36), nullable=False)
    amount = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    corporate = relationship("CorporateCustomer", lazy="selectin")
    requester = relationship("Customer", lazy="selectin")
    origin_account = relationship("Account", lazy="selectin")
