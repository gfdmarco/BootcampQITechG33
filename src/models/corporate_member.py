from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.customer import Customer
from models.corporate_customer import CorporateCustomer

class CorporateMember(Base):
    __tablename__ = "corporate_member"

    id = Column(Integer, primary_key=True)
    corporate_id = Column(Integer, ForeignKey("corporate_customer.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey(Customer.id), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("corporate_id", "customer_id"),
    )

    corporate = relationship("CorporateCustomer", back_populates="members", lazy="selectin")
    customer = relationship("Customer", lazy="selectin")
