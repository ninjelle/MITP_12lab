from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut, ClientListItem
from app.schemas.contact import ContactOut
from app.schemas.deal import DealOut

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=List[ClientListItem])
def list_clients(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    manager_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Client)
    if current_user.role == "manager":
        q = q.filter(Client.assigned_manager_id == current_user.id)
    if status:
        q = q.filter(Client.status == status)
    if search:
        q = q.filter(Client.company_name.ilike(f"%{search}%"))
    if manager_id:
        q = q.filter(Client.assigned_manager_id == manager_id)
    return q.order_by(Client.created_at.desc()).offset(skip).limit(limit).all()


@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot create clients")
    client = Client(**data.model_dump())
    if not client.assigned_manager_id:
        client.assigned_manager_id = current_user.id
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).options(
        joinedload(Client.contacts),
        joinedload(Client.deals),
    ).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.role == "manager" and client.assigned_manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return client


@router.get("/{client_id}/contacts", response_model=List[ContactOut])
def get_client_contacts(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client.contacts


@router.get("/{client_id}/deals", response_model=List[DealOut])
def get_client_deals(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client.deals


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot update clients")
    if current_user.role == "manager" and client.assigned_manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Only admins can delete clients")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
