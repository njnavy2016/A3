# Sensors 路由
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime, timedelta
from ..database import get_db
from .. import models, schemas
from ..services.redis_client import redis_client

router = APIRouter()


@router.get("", response_model=List[schemas.SensorOut])
def list_sensors(
    equipment_id: Optional[int] = Query(None),
    sensor_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Sensor)
    if equipment_id:
        query = query.filter(models.Sensor.equipment_id == equipment_id)
    if sensor_type:
        query = query.filter(models.Sensor.sensor_type == sensor_type)
    return query.all()


@router.get("/{sensor_id}", response_model=schemas.SensorOut)
def get_sensor(sensor_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if not s:
        raise HTTPException(404, "传感器不存在")
    return s


@router.get("/{sensor_id}/realtime")
async def get_sensor_realtime(sensor_id: int, db: Session = Depends(get_db)):
    """从 Redis 拉取该传感器最近的实时数据"""
    sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if not sensor:
        raise HTTPException(404, "传感器不存在")
    
    eq = db.query(models.Equipment).filter(models.Equipment.id == sensor.equipment_id).first()
    
    rd = redis_client.redis
    if rd is None or eq is None:
        return {"points": []}
    
    # 从 ZSet 取最近 360 个点（约 6 小时@1分钟）
    key = f"ts:{eq.equipment_code}:{sensor.sensor_code}"
    results = await rd.zrange(key, -360, -1, withscores=True)
    
    points = []
    for raw, ts in results:
        try:
            data = json.loads(raw)
            points.append({
                "ts": data.get("t"),
                "value": data.get("v"),
                "timestamp_epoch": ts,
            })
        except Exception:
            pass
    
    return {
        "sensor_code": sensor.sensor_code,
        "equipment_code": eq.equipment_code if eq else None,
        "points": points,
    }
