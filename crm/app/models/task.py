from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), default="follow_up")
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="open")
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships — foreign_keys указаны явно, т.к. два FK на users
    client = relationship("Client", back_populates="tasks")
    deal = relationship("Deal", back_populates="tasks")
    assigned_to = relationship(
        "User",
        foreign_keys=[assigned_to_id],
        back_populates="tasks"
    )
    created_by = relationship(
        "User",
        foreign_keys=[created_by_id]
    )