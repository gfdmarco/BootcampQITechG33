from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, BigInteger, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.loan import Loan

class LoanInstallment(Base):
    __tablename__ = "loan_installment"

    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey(Loan.id), nullable=False)
    installment_number = Column(Integer, nullable=False)
    amount = Column(BigInteger, nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    loan = relationship("Loan", foreign_keys=[loan_id], back_populates="installments", lazy="selectin")
