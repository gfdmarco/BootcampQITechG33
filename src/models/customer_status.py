from sqlalchemy import CHAR, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base

class CustomerStatus(Base):
    __tablename__ = "customer_status"
    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("enumerator"),)

    CREATED = "created"
    PENDING = "pending"
    FAILED = "failed"
    SUCCESS = "success"