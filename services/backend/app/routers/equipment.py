# Equipment 路由
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from .. import models, schemas

router = APIRouter()


@router.get("", response_model=List[schemas.EquipmentOut])
def list_equipments(
    equipment_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Equipment)
    if equipment_type:
        query = query.filter(models.Equipment.equipment_type == equipment_type)
    if status:
        query = query.filter(models.Equipment.status == status)
    return query.order_by(models.Equipment.id).all()


@router.get("/{equipment_id}", response_model=schemas.EquipmentOut)
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    eq = db.query(models.Equipment).filter(models.Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(404, "设备不存在")
    return eq


@router.post("", response_model=schemas.EquipmentOut)
def create_equipment(data: schemas.EquipmentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Equipment).filter(
        models.Equipment.equipment_code == data.equipment_code
    ).first()
    if existing:
        raise HTTPException(400, "设备编码已存在")
    
    eq = models.Equipment(**data.model_dump())
    db.add(eq)
    db.commit()
    db.refresh(eq)
    return eq


@router.patch("/{equipment_id}", response_model=schemas.EquipmentOut)
def update_equipment(
    equipment_id: int,
    data: schemas.EquipmentUpdate,
    db: Session = Depends(get_db),
):
    eq = db.query(models.Equipment).filter(models.Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(404, "设备不存在")
    
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(eq, key, val)
    db.commit()
    db.refresh(eq)
    return eq


@router.delete("/{equipment_id}")
def delete_equipment(equipment_id: int, db: Session = Depends(get_db)):
    eq = db.query(models.Equipment).filter(models.Equipment.id == equipment_id).first()
    if not eq:
        raise HTTPException(404, "设备不存在")
    db.delete(eq)
    db.commit()
    return {"message": "删除成功"}


@router.get("/{equipment_id}/sensors", response_model=List[schemas.SensorOut])
def get_equipment_sensors(equipment_id: int, db: Session = Depends(get_db)):
    return db.query(models.Sensor).filter(
        models.Sensor.equipment_id == equipment_id
    ).order_by(models.Sensor.sensor_code).all()
