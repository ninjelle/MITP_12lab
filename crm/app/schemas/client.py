from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.schemas.contact import ContactOut
    from app.schemas.deal import DealOut


class ClientBase(BaseModel):
    company_name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = "lead"
    notes: Optional[str] = None
    assigned_manager_id: Optional[int] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_manager_id: Optional[int] = None


class ClientOut(ClientBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClientDetail(ClientOut):
    contacts: List[ContactOut] = []
    deals: List[DealOut] = []


class ClientListItem(BaseModel):
    id: int
    company_name: str
    industry: Optional[str] = None
    status: str
    city: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True