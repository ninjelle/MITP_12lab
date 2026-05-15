from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: Optional[str] = "follow_up"
    priority: Optional[str] = "medium"
    status: Optional[str] = "open"
    due_date: Optional[date] = None
    client_id: Optional[int] = None
    deal_id: Optional[int] = None
    assigned_to_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    client_id: Optional[int] = None
    deal_id: Optional[int] = None
    assigned_to_id: Optional[int] = None


class TaskOut(TaskBase):
    id: int
    created_by_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
