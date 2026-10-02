from sqlalchemy import Column, Integer, String, DateTime, func
from models.base import Base

class CorporateStatus(Base):
    __tablename__ = "corporate_status"

    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(20), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
