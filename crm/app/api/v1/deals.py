from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.deal import Deal, STAGE_ORDER, STAGE_DEFAULT_PROBABILITY
from app.models.user import User
from app.schemas.deal import DealCreate, DealUpdate, DealOut

router = APIRouter(prefix="/deals", tags=["Deals"])


@router.get("", response_model=List[DealOut])
def list_deals(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    stage: Optional[str] = None,
    client_id: Optional[int] = None,
    manager_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Deal)
    if current_user.role == "manager":
        q = q.filter(Deal.assigned_manager_id == current_user.id)
    if stage:
        q = q.filter(Deal.stage == stage)
    if client_id:
        q = q.filter(Deal.client_id == client_id)
    if manager_id:
        q = q.filter(Deal.assigned_manager_id == manager_id)
    return q.order_by(Deal.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/pipeline", response_model=Dict)
def get_pipeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sales funnel: deals grouped by stage with totals."""
    q = db.query(Deal)
    if current_user.role == "manager":
        q = q.filter(Deal.assigned_manager_id == current_user.id)
    deals = q.all()
    pipeline = {stage: {"count": 0, "total_amount": 0.0, "deals": []} for stage in STAGE_ORDER}
    for deal in deals:
        if deal.stage in pipeline:
            pipeline[deal.stage]["count"] += 1
            pipeline[deal.stage]["total_amount"] += deal.amount or 0
            pipeline[deal.stage]["deals"].append({
                "id": deal.id,
                "title": deal.title,
                "amount": deal.amount,
                "probability": deal.probability,
                "client_id": deal.client_id,
            })
    return pipeline


@router.post("", response_model=DealOut, status_code=201)
def create_deal(
    data: DealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot create deals")
    deal_data = data.model_dump()
    if deal_data.get("stage") and deal_data.get("stage") in STAGE_DEFAULT_PROBABILITY:
        if not deal_data.get("probability"):
            deal_data["probability"] = STAGE_DEFAULT_PROBABILITY[deal_data["stage"]]
    deal = Deal(**deal_data)
    if not deal.assigned_manager_id:
        deal.assigned_manager_id = current_user.id
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    if current_user.role == "manager" and deal.assigned_manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return deal


@router.put("/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: int,
    data: DealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot update deals")
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    if current_user.role == "manager" and deal.assigned_manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    update_data = data.model_dump(exclude_unset=True)
    # Auto-set probability on stage change
    if "stage" in update_data and "probability" not in update_data:
        update_data["probability"] = STAGE_DEFAULT_PROBABILITY.get(update_data["stage"], deal.probability)
    # Auto-set close date when deal closes
    if update_data.get("stage") in ("closed_won", "closed_lost") and not deal.actual_close_date:
        from datetime import date
        update_data["actual_close_date"] = date.today()
    for field, value in update_data.items():
        setattr(deal, field, value)
    db.commit()
    db.refresh(deal)
    return deal


@router.delete("/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin",):
        raise HTTPException(status_code=403, detail="Only admins can delete deals")
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    db.delete(deal)
    db.commit()
