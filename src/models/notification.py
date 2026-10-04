from sqlalchemy import CHAR, Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint, func
from models.base import Base


class Notification(Base):
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True)
    key = Column(CHAR(36), nullable=False)
    event_key = Column(String(120), nullable=False)
    customer_key = Column(CHAR(36), nullable=False)
    title = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("key"),
        UniqueConstraint("event_key"),
    )
