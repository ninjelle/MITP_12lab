from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    assigned_manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    stage = Column(String(50), default="qualification")
    # Stages: qualification → needs_analysis → proposal → negotiation → closed_won → closed_lost
    amount = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    probability = Column(Integer, default=10)  # 0-100%
    expected_close_date = Column(Date, nullable=True)
    actual_close_date = Column(Date, nullable=True)
    source = Column(String(100))   # e.g. website, referral, cold_call
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="deals")
    assigned_manager = relationship("User", back_populates="deals")
    tasks = relationship("Task", back_populates="deal")


STAGE_ORDER = [
    "qualification",
    "needs_analysis",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
]

STAGE_DEFAULT_PROBABILITY = {
    "qualification": 10,
    "needs_analysis": 25,
    "proposal": 50,
    "negotiation": 75,
    "closed_won": 100,
    "closed_lost": 0,
}
