from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=List[TaskOut])
def list_tasks(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    client_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Task)
    if current_user.role == "manager":
        q = q.filter(Task.assigned_to_id == current_user.id)
    if status:
        q = q.filter(Task.status == status)
    if priority:
        q = q.filter(Task.priority == priority)
    if assigned_to_id:
        q = q.filter(Task.assigned_to_id == assigned_to_id)
    if client_id:
        q = q.filter(Task.client_id == client_id)
    if deal_id:
        q = q.filter(Task.deal_id == deal_id)
    if overdue_only:
        q = q.filter(Task.due_date < date.today(), Task.status.notin_(["done", "cancelled"]))
    return q.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).offset(skip).limit(limit).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot create tasks")
    task = Task(**data.model_dump(), created_by_id=current_user.id)
    if not task.assigned_to_id:
        task.assigned_to_id = current_user.id
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot update tasks")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = data.model_dump(exclude_unset=True)
    # Auto-set completed_at when marking done
    if update_data.get("status") == "done" and not task.completed_at:
        update_data["completed_at"] = datetime.utcnow()
    for field, value in update_data.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot delete tasks")
    if current_user.role == "manager" and task.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    db.delete(task)
    db.commit()
