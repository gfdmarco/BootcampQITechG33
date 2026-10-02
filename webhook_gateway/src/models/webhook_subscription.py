from sqlalchemy import Column, Integer, String, DateTime, ARRAY, func
from models.base import Base


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscription"

    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"

    id = Column(Integer, primary_key=True)
    key = Column(String(36), nullable=False, unique=True)
    owner_corporate_key = Column(String(36), nullable=False)
    target_url = Column(String(500), nullable=False)
    secret_hash = Column(String(255), nullable=False)
    event_types = Column(ARRAY(String), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())