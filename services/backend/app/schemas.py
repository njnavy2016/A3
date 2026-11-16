# Pydantic Schemas（请求/响应模型）
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List, Any


# ========== Equipment ==========
class EquipmentOut(BaseModel):
    id: int
    equipment_code: str
    name: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    install_date: Optional[date] = None
    location: Optional[str] = None
    equipment_type: str
    health_score: float
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EquipmentCreate(BaseModel):
    equipment_code: str
    name: str
    equipment_type: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    install_date: Optional[date] = None
    location: Optional[str] = None


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    health_score: Optional[float] = None
    status: Optional[str] = None


# ========== Sensor ==========
class SensorOut(BaseModel):
    id: int
    equipment_id: int
    sensor_code: str
    sensor_type: str
    channel: Optional[str] = None
    unit: Optional[str] = None
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    baseline_value: Optional[float] = None

    class Config:
        from_attributes = True


# ========== Alert ==========
class AlertOut(BaseModel):
    id: int
    equipment_id: int
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    feature_snapshot: Optional[dict] = None
    rul_hours: Optional[int] = None
    risk_score: Optional[float] = None
    status: str
    agent_diagnosis: Optional[str] = None
    agent_rca: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertAck(BaseModel):
    comment: Optional[str] = None


# ========== Work Order ==========
class SparePart(BaseModel):
    name: str
    part_no: Optional[str] = None
    qty: int = 1
    unit_price: Optional[float] = None


class WorkOrderOut(BaseModel):
    id: int
    order_no: str
    alert_id: Optional[int] = None
    equipment_id: int
    order_type: str
    title: str
    description: Optional[str] = None
    diagnosis: Optional[str] = None
    spare_parts: Optional[List[SparePart]] = None
    status: str
    priority: str
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    requires_human_approval: bool = True
    approval_policy: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkOrderCreate(BaseModel):
    equipment_id: int
    order_type: str
    title: str
    description: Optional[str] = None
    diagnosis: Optional[str] = None
    spare_parts: Optional[List[SparePart]] = None
    priority: Optional[str] = None
    requires_human_approval: Optional[bool] = None


class WorkOrderUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    diagnosis: Optional[str] = None


# ========== Approval ==========
class ApprovalAction(BaseModel):
    action: str = Field(..., description="APPROVE / REJECT / EDIT")
    comment: Optional[str] = None
    edited_fields: Optional[dict] = None   # EDIT 时修改的字段
    approver: str = "demo_user"
    approver_role: str = "TECHNICIAN_LEAD"


class ApprovalRecordOut(BaseModel):
    id: int
    work_order_id: int
    action: str
    comment: Optional[str] = None
    edited_payload: Optional[dict] = None
    approver: str
    approver_role: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== Manual ==========
class ManualChunkOut(BaseModel):
    id: int
    chapter: Optional[str] = None
    section_title: Optional[str] = None
    content: str
    keywords: Optional[str] = None

    class Config:
        from_attributes = True


# ========== 统计/聚合 ==========
class HealthOverview(BaseModel):
    total_equipment: int
    avg_health_score: float
    open_alerts: int
    pending_work_orders: int
    critical_alerts: int
    recent_trends: List[dict] = []


class DashboardStats(BaseModel):
    equipment_summary: List[dict]
    recent_alerts: List[AlertOut]
    pending_approvals: int
    critical_count: int
