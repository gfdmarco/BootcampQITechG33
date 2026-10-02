from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.customer import Customer

class CorporateAudit(Base):
    __tablename__ = "corporate_audit"

    id = Column(Integer, primary_key=True)
    corporate_id = Column(Integer, ForeignKey("corporate_customer.id"), nullable=False)
    actor_customer_id = Column(Integer, ForeignKey(Customer.id))
    action = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    corporate = relationship("CorporateCustomer", lazy="selectin")
    actor = relationship("Customer", lazy="selectin")
