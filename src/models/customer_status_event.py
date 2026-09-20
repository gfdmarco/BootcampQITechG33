from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from models.base import Base
from sqlalchemy.orm import relationship


class CustomerStatusEvent(Base):
    __tablename__ = "customer_status_event"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    from_status_id = Column(Integer, ForeignKey("customer_status.id"), nullable=True)
    to_status_id = Column(Integer, ForeignKey("customer_status.id"), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    customer = relationship(
        "Customer",
        foreign_keys=[customer_id],
        back_populates="status_events",
        lazy="selectin",
    )
    from_status = relationship("CustomerStatus", foreign_keys=[from_status_id], lazy="selectin")
    to_status = relationship("CustomerStatus", foreign_keys=[to_status_id], lazy="selectin")
