from sqlalchemy import Column, Integer, String, Numeric, DateTime, UniqueConstraint, func
from models.base import Base


class Fee(Base):
    __tablename__ = "fee"

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("type"),)

    PIX = "pix"
    TED = "ted"
    CARD = "card"
    INTERNATIONAL = "international"