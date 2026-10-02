from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, JSON, func
from models.base import Base


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"

    STATUS_PENDING = "pending"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_DEAD = "dead"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("webhook_subscription.id"), nullable=False)
    event_id = Column(String(36), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    last_status_code = Column(Integer, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())