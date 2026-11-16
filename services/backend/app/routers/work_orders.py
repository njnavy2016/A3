# Work Orders 路由
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from datetime import datetime
import uuid
from ..database import get_db
from .. import models, schemas

router = APIRouter()


def _generate_order_no() -> str:
    """生成工单编号"""
    now = datetime.now()
    return f"WO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


@router.get("", response_model=List[schemas.WorkOrderOut])
def list_work_orders(
    equipment_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.WorkOrder)
    if equipment_id:
        query = query.filter(models.WorkOrder.equipment_id == equipment_id)
    if status:
        query = query.filter(models.WorkOrder.status == status)
    if order_type:
        query = query.filter(models.WorkOrder.order_type == order_type)
    return query.order_by(desc(models.WorkOrder.created_at)).limit(limit).all()


@router.get("/pending-count")
def pending_count(db: Session = Depends(get_db)):
    """待审批工单计数"""
    count = db.query(func.count(models.WorkOrder.id)).filter(
        models.WorkOrder.status == 'PENDING_APPROVAL'
    ).scalar() or 0
    return {"pending_approval_count": count}


@router.get("/{work_order_id}", response_model=schemas.WorkOrderOut)
def get_work_order(work_order_id: int, db: Session = Depends(get_db)):
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    return wo


@router.post("", response_model=schemas.WorkOrderOut)
def create_work_order(
    data: schemas.WorkOrderCreate,
    db: Session = Depends(get_db),
):
    # 验证设备
    eq = db.query(models.Equipment).filter(models.Equipment.id == data.equipment_id).first()
    if not eq:
        raise HTTPException(404, "设备不存在")
    
    order = models.WorkOrder(
        order_no=_generate_order_no(),
        equipment_id=data.equipment_id,
        alert_id=None,  # 手动创建的工单无关联告警
        order_type=data.order_type,
        title=data.title,
        description=data.description,
        diagnosis=data.diagnosis,
        spare_parts=[sp.model_dump() for sp in (data.spare_parts or [])],
        priority=data.priority or "MEDIUM",
        requires_human_approval=data.requires_human_approval if data.requires_human_approval is not None else True,
        approval_policy="LEVEL1",
        created_by="MANUAL",
        status="DRAFT" if (data.requires_human_approval is not False) else "PENDING_APPROVAL",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{work_order_id}", response_model=schemas.WorkOrderOut)
def update_work_order(
    work_order_id: int,
    data: schemas.WorkOrderUpdate,
    db: Session = Depends(get_db),
):
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(wo, key, val)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/{work_order_id}/submit")
def submit_for_approval(work_order_id: int, db: Session = Depends(get_db)):
    """提交审批"""
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    if wo.status not in ('DRAFT', 'REJECTED'):
        raise HTTPException(400, f"当前状态 {wo.status} 不能提交")
    
    wo.status = 'PENDING_APPROVAL'
    db.commit()
    return {"message": "已提交审批", "order_no": wo.order_no}


@router.post("/{work_order_id}/start")
def start_work(work_order_id: int, db: Session = Depends(get_db)):
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    if wo.status != 'APPROVED':
        raise HTTPException(400, "只有已批准的工单才能开始执行")
    
    wo.status = 'IN_PROGRESS'
    wo.actual_start = datetime.now()
    db.commit()
    return {"message": "工单开始执行"}


@router.post("/{work_order_id}/complete")
def complete_work(work_order_id: int, db: Session = Depends(get_db)):
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    if wo.status != 'IN_PROGRESS':
        raise HTTPException(400, "只有执行中的工单才能完成")
    
    wo.status = 'COMPLETED'
    wo.actual_end = datetime.now()
    db.commit()
    return {"message": "工单已完成"}
