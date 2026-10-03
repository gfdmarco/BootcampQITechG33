from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.corporate_status import CorporateStatus

class CorporateCustomer(Base):
    __tablename__ = "corporate_customer"

    id = Column(Integer, primary_key=True)
    corporate_key = Column(CHAR(36), nullable=False, unique=True)
    cnpj = Column(CHAR(14), nullable=False, unique=True)
    company_name = Column(String(255), nullable=False)
    trade_name = Column(String(255))
    status_id = Column(Integer, ForeignKey(CorporateStatus.id), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    status = relationship("CorporateStatus", lazy="selectin")
    members = relationship("CorporateMember", back_populates="corporate", lazy="selectin")
    accounts = relationship("CorporateAccount", back_populates="corporate", lazy="selectin")
