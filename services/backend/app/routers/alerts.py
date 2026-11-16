# Alerts 路由
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from .. import models, schemas

router = APIRouter()


@router.get("", response_model=List[schemas.AlertOut])
def list_alerts(
    equipment_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.Alert)
    if equipment_id:
        query = query.filter(models.Alert.equipment_id == equipment_id)
    if status:
        query = query.filter(models.Alert.status == status)
    if severity:
        query = query.filter(models.Alert.severity == severity)
    if alert_type:
        query = query.filter(models.Alert.alert_type == alert_type)
    return query.order_by(desc(models.Alert.created_at)).limit(limit).all()


@router.get("/{alert_id}", response_model=schemas.AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "告警不存在")
    return alert


@router.patch("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    comment: Optional[str] = None,
    db: Session = Depends(get_db),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "告警不存在")
    alert.status = 'ACKNOWLEDGED'
    alert.acknowledged_at = datetime.now()
    db.commit()
    return {"message": "已确认", "status": alert.status}


@router.patch("/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "告警不存在")
    alert.status = 'RESOLVED'
    alert.resolved_at = datetime.now()
    db.commit()
    return {"message": "已解决", "status": alert.status}


@router.post("", response_model=schemas.AlertOut)
def create_alert_manual(
    data: schemas.AlertOut,
    db: Session = Depends(get_db),
):
    """手动创建告警"""
    alert = models.Alert(
        equipment_id=data.equipment_id,
        alert_type=data.alert_type,
        severity=data.severity,
        title=data.title,
        description=data.description,
        created_by="MANUAL",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
