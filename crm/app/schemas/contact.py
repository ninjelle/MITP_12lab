from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class ContactBase(BaseModel):
    client_id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    is_primary: Optional[bool] = False
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class ContactOut(ContactBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
