from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class DealBase(BaseModel):
    title: str
    client_id: int
    assigned_manager_id: Optional[int] = None
    stage: Optional[str] = "qualification"
    amount: Optional[float] = 0.0
    currency: Optional[str] = "USD"
    probability: Optional[int] = 10
    expected_close_date: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    title: Optional[str] = None
    assigned_manager_id: Optional[int] = None
    stage: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    probability: Optional[int] = None
    expected_close_date: Optional[date] = None
    actual_close_date: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class DealOut(DealBase):
    id: int
    actual_close_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
