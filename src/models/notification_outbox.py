from sqlalchemy import CHAR, Column, DateTime, Integer, String, Text, UniqueConstraint, func

from models.base import Base


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True)
    event_key = Column(String(120), nullable=False)
    customer_key = Column(CHAR(36), nullable=False)
    title = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_key"),
    )
