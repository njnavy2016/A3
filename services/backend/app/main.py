# FastAPI 主入口
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
import redis.asyncio as aioredis
import json
from datetime import datetime, timedelta

from .config import settings
from .database import get_db, engine, SessionLocal
from . import models, schemas
from .routers import equipment, sensors, alerts, work_orders, approvals, manuals, agent
from .services.redis_client import redis_client


app = FastAPI(
    title="PdM Agent Backend API",
    version="1.0.0",
    description="关键工业设备可预测性维护系统后端",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册子路由
app.include_router(equipment.router, prefix="/api/v1/equipment", tags=["设备管理"])
app.include_router(sensors.router, prefix="/api/v1/sensors", tags=["传感器"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["告警管理"])
app.include_router(work_orders.router, prefix="/api/v1/work-orders", tags=["工单管理"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["审批"])
app.include_router(manuals.router, prefix="/api/v1/manuals", tags=["维修手册"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["智能体"])


@app.on_event("startup")
async def on_startup():
    """启动时初始化 Redis 连接"""
    await redis_client.connect()
    print("[Backend] 启动完成，服务就绪")


@app.on_event("shutdown")
async def on_shutdown():
    await redis_client.disconnect()


# ========== 基础端点 ==========

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "backend", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/dashboard/stats")
async def dashboard_stats(db: Session = Depends(get_db)):
    """Dashboard 统计数据"""
    total_eq = db.query(func.count(models.Equipment.id)).scalar() or 0
    avg_health = db.query(func.avg(models.Equipment.health_score)).scalar() or 0
    open_alerts = db.query(func.count(models.Alert.id)).filter(models.Alert.status == 'OPEN').scalar() or 0
    pending_wos = db.query(func.count(models.WorkOrder.id)).filter(
        models.WorkOrder.status.in_(['PENDING_APPROVAL', 'DRAFT'])
    ).scalar() or 0
    critical_alerts = db.query(func.count(models.Alert.id)).filter(
        models.Alert.severity == 'CRITICAL',
        models.Alert.status.in_(['OPEN', 'ACKNOWLEDGED'])
    ).scalar() or 0
    
    equipment_list = db.query(models.Equipment).all()
    recent_alerts = db.query(models.Alert).order_by(models.Alert.created_at.desc()).limit(10).all()
    
    return {
        "total_equipment": total_eq,
        "avg_health_score": round(float(avg_health) if avg_health else 0, 2),
        "open_alerts": open_alerts,
        "pending_work_orders": pending_wos,
        "critical_alerts": critical_alerts,
        "equipment_summary": [
            {
                "id": eq.id,
                "code": eq.equipment_code,
                "name": eq.name,
                "health": float(eq.health_score or 100),
                "status": eq.status,
                "type": eq.equipment_type,
            }
            for eq in equipment_list
        ],
        "recent_alerts": [schemas.AlertOut.model_validate(a).model_dump() for a in recent_alerts],
    }


@app.get("/api/v1/realtime/latest")
async def get_latest_from_redis(
    equipment_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """从 Redis 拉取最新传感器数据"""
    rd = redis_client.redis
    if rd is None:
        raise HTTPException(503, "Redis 未连接")
    
    # 确定设备列表
    if equipment_code:
        codes = [equipment_code]
    else:
        codes = [eq.equipment_code for eq in db.query(models.Equipment).all()]
    
    result = {}
    for code in codes:
        result[code] = {}
        # 查出该设备的所有 sensor_code
        sensors = db.query(models.Sensor).join(
            models.Equipment, models.Equipment.id == models.Sensor.equipment_id
        ).filter(models.Equipment.equipment_code == code).all()
        
        for sensor in sensors:
            key = f"latest:{code}:{sensor.sensor_code}"
            val = await rd.get(key)
            if val:
                try:
                    data = json.loads(val)
                    result[code][sensor.sensor_code] = data
                except Exception:
                    pass
    
    return result
