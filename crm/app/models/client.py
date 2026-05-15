from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    industry = Column(String(100))
    website = Column(String(255))
    address = Column(Text)
    city = Column(String(100))
    country = Column(String(100))
    status = Column(String(50), default="lead")
    notes = Column(Text)
    assigned_manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    assigned_manager = relationship("User", back_populates="clients")
    contacts = relationship("Contact", back_populates="client", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="client", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="client")
