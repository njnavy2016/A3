# Approvals 路由 —— 核心 HITL 拦截
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime
import uuid
from ..database import get_db
from .. import models, schemas

router = APIRouter()


@router.get("", response_model=List[schemas.WorkOrderOut])
def list_pending_approvals(db: Session = Depends(get_db)):
    """列出所有待审批工单"""
    return db.query(models.WorkOrder).filter(
        models.WorkOrder.status == 'PENDING_APPROVAL'
    ).order_by(desc(models.WorkOrder.created_at)).all()


@router.post("/{work_order_id}/action", response_model=schemas.WorkOrderOut)
def handle_approval(
    work_order_id: int,
    action: schemas.ApprovalAction,
    db: Session = Depends(get_db),
):
    """
    审批操作：APPROVE / REJECT / EDIT
    
    审批拦截器的核心——这里是最后一道防线：
    即使 Agent 绕过前端直接调 API，Backend 也会在这里强制执行审批策略。
    """
    wo = db.query(models.WorkOrder).filter(models.WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(404, "工单不存在")
    
    if wo.status != 'PENDING_APPROVAL':
        raise HTTPException(400, f"工单当前状态 {wo.status}，无需审批")
    
    # ====== 核心安全校验 ======
    # 停机申请（SHUTDOWN_REQUEST）必须 SUPERVISOR 或更高审批
    if wo.order_type == 'SHUTDOWN_REQUEST':
        if action.action == 'APPROVE' and action.approver_role not in ('SUPERVISOR', 'MANAGER'):
            raise HTTPException(
                status_code=403,
                detail="⚠️ 安全拦截：停机申请必须由 SUPERVISOR 或 MANAGER 审批",
            )
    
    # CRITICAL 风险下的紧急工单也需要 Manager 级别
    if wo.priority == 'CRITICAL' and action.action == 'APPROVE':
        if action.approver_role not in ('MANAGER', 'SUPERVISOR'):
            raise HTTPException(
                status_code=403,
                detail="⚠️ 安全拦截：CRITICAL 优先级工单需 SUPERVISOR/MANAGER 审批",
            )
    
    # ====== 执行审批 ======
    record = models.ApprovalRecord(
        work_order_id=work_order_id,
        action=action.action,
        comment=action.comment,
        edited_payload=action.edited_fields,
        approver=action.approver,
        approver_role=action.approver_role,
    )
    db.add(record)
    
    if action.action == 'APPROVE':
        wo.status = 'APPROVED'
        wo.approved_by = action.approver
        wo.approved_at = datetime.now()
    elif action.action == 'REJECT':
        wo.status = 'REJECTED'
        wo.rejected_reason = action.comment or "无理由"
    elif action.action == 'EDIT':
        # 应用编辑后的字段
        if action.edited_fields:
            for key, val in action.edited_fields.items():
                if hasattr(wo, key) and key not in ('id', 'order_no', 'status'):
                    setattr(wo, key, val)
        # 编辑后保持 PENDING_APPROVAL 状态，等待再次审批（除非自动通过）
        wo.status = 'PENDING_APPROVAL'
    elif action.action == 'ESCALATE':
        # 升级：保持 PENDING_APPROVAL，但标记
        wo.approval_policy = 'ESCALATE'
    
    db.commit()
    db.refresh(wo)
    return wo


@router.get("/{work_order_id}/records", response_model=List[schemas.ApprovalRecordOut])
def list_approval_records(work_order_id: int, db: Session = Depends(get_db)):
    """查看审批历史"""
    return db.query(models.ApprovalRecord).filter(
        models.ApprovalRecord.work_order_id == work_order_id
    ).order_by(models.ApprovalRecord.created_at.asc()).all()
