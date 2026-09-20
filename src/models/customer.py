from sqlalchemy import CHAR, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base


class Customer(Base):
    __tablename__ = "customer"

    id = Column(Integer, primary_key=True)
    customer_key = Column(CHAR(36), nullable=False)
    name = Column(String(255), nullable=False)
    document_number = Column(CHAR(14), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=False)
    status_id = Column(Integer, ForeignKey("customer_status.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("customer_key"),
        UniqueConstraint("document_number"),
        UniqueConstraint("email"),
    )

    status = relationship("CustomerStatus", foreign_keys=[status_id], lazy="selectin")

    status_events = relationship(
        "CustomerStatusEvent",
        back_populates="customer",
        order_by="asc(CustomerStatusEvent.created_at)",
    )
