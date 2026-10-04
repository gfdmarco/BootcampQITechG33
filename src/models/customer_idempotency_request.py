from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from models.base import Base


class CustomerIdempotencyRequest(Base):
    __tablename__ = "customer_idempotency_request"

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String(120), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    request_hash = Column(CHAR(64), nullable=False)
    response_status = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    customer = relationship("Customer", lazy="selectin")
