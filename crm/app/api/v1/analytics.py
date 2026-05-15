from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from typing import Optional
from datetime import date, timedelta
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client import Client
from app.models.deal import Deal, STAGE_ORDER
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """High-level KPIs for dashboard."""
    is_manager = current_user.role == "manager"

    # Clients
    client_q = db.query(func.count(Client.id))
    if is_manager:
        client_q = client_q.filter(Client.assigned_manager_id == current_user.id)
    total_clients = client_q.scalar()

    # Deals
    deal_q = db.query(Deal)
    if is_manager:
        deal_q = deal_q.filter(Deal.assigned_manager_id == current_user.id)
    deals = deal_q.all()

    open_deals = [d for d in deals if d.stage not in ("closed_won", "closed_lost")]
    won_deals = [d for d in deals if d.stage == "closed_won"]
    lost_deals = [d for d in deals if d.stage == "closed_lost"]

    total_pipeline = sum(d.amount or 0 for d in open_deals)
    total_won = sum(d.amount or 0 for d in won_deals)
    weighted_pipeline = sum((d.amount or 0) * (d.probability or 0) / 100 for d in open_deals)

    win_rate = round(len(won_deals) / max(len(won_deals) + len(lost_deals), 1) * 100, 1)

    # Tasks
    task_q = db.query(Task)
    if is_manager:
        task_q = task_q.filter(Task.assigned_to_id == current_user.id)
    tasks = task_q.all()
    open_tasks = len([t for t in tasks if t.status == "open"])
    overdue_tasks = len([
        t for t in tasks
        if t.status not in ("done", "cancelled") and t.due_date and t.due_date < date.today()
    ])

    return {
        "clients": {
            "total": total_clients,
        },
        "deals": {
            "total": len(deals),
            "open": len(open_deals),
            "won": len(won_deals),
            "lost": len(lost_deals),
            "win_rate_pct": win_rate,
            "total_pipeline_value": round(total_pipeline, 2),
            "total_won_value": round(total_won, 2),
            "weighted_pipeline": round(weighted_pipeline, 2),
        },
        "tasks": {
            "open": open_tasks,
            "overdue": overdue_tasks,
        },
    }


@router.get("/pipeline-funnel")
def pipeline_funnel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deal counts and amounts per funnel stage."""
    q = db.query(
        Deal.stage,
        func.count(Deal.id).label("count"),
        func.coalesce(func.sum(Deal.amount), 0).label("total_amount"),
    ).group_by(Deal.stage)
    if current_user.role == "manager":
        q = q.filter(Deal.assigned_manager_id == current_user.id)
    rows = q.all()
    stage_map = {r.stage: {"count": r.count, "total_amount": float(r.total_amount)} for r in rows}
    return [
        {"stage": s, **stage_map.get(s, {"count": 0, "total_amount": 0.0})}
        for s in STAGE_ORDER
    ]


@router.get("/deals-by-month")
def deals_by_month(
    months: int = Query(default=6, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Won/lost deal counts grouped by closing month."""
    start_date = date.today() - timedelta(days=months * 30)
    q = db.query(Deal).filter(
        Deal.actual_close_date >= start_date,
        Deal.stage.in_(["closed_won", "closed_lost"]),
    )
    if current_user.role == "manager":
        q = q.filter(Deal.assigned_manager_id == current_user.id)
    deals = q.all()
    buckets: dict = {}
    for d in deals:
        key = d.actual_close_date.strftime("%Y-%m")
        if key not in buckets:
            buckets[key] = {"month": key, "won": 0, "lost": 0, "won_value": 0.0, "lost_value": 0.0}
        if d.stage == "closed_won":
            buckets[key]["won"] += 1
            buckets[key]["won_value"] += d.amount or 0
        else:
            buckets[key]["lost"] += 1
            buckets[key]["lost_value"] += d.amount or 0
    return sorted(buckets.values(), key=lambda x: x["month"])


@router.get("/clients-by-status")
def clients_by_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Client.status, func.count(Client.id).label("count")).group_by(Client.status)
    if current_user.role == "manager":
        q = q.filter(Client.assigned_manager_id == current_user.id)
    return [{"status": r.status, "count": r.count} for r in q.all()]


@router.get("/manager-performance")
def manager_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-manager stats (admin only)."""
    if current_user.role != "admin":
        # return just current user's stats
        managers = [current_user]
    else:
        managers = db.query(User).filter(User.role.in_(["admin", "manager"]), User.is_active == True).all()

    result = []
    for mgr in managers:
        deals = db.query(Deal).filter(Deal.assigned_manager_id == mgr.id).all()
        won = [d for d in deals if d.stage == "closed_won"]
        lost = [d for d in deals if d.stage == "closed_lost"]
        result.append({
            "manager_id": mgr.id,
            "manager_name": mgr.full_name,
            "total_deals": len(deals),
            "won_deals": len(won),
            "lost_deals": len(lost),
            "win_rate_pct": round(len(won) / max(len(won) + len(lost), 1) * 100, 1),
            "total_won_value": round(sum(d.amount or 0 for d in won), 2),
        })
    return result
