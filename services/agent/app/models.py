# 数据库模型（与 Backend 共享，此处引入独立副本以避免循环依赖）
from sqlalchemy import Column, String, Integer, BigInteger, Float, DateTime, Text, Boolean, Index, ForeignKey
from sqlalchemy.dialects.mysql import ENUM as MysqlEnum, JSON, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment_code = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    model = Column(String(128))
    manufacturer = Column(String(128))
    install_date = Column(String(10))
    location = Column(String(255))
    equipment_type = Column(MysqlEnum('CNC_SPINDLE', 'COMPRESSOR', 'WIND_GEARBOX'), nullable=False)
    health_score = Column(DECIMAL(5, 2), default=100.00)
    status = Column(MysqlEnum('RUNNING', 'STOPPED', 'MAINTENANCE', 'CRITICAL'), default='RUNNING')
    created_at = Column(DateTime, server_default=func.now())


class Sensor(Base):
    __tablename__ = "sensor"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id = Column(BigInteger, ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    sensor_code = Column(String(64), nullable=False)
    sensor_type = Column(MysqlEnum('TEMPERATURE', 'VIBRATION', 'CURRENT', 'OIL_PRESSURE', 'SPECTRUM'), nullable=False)
    channel = Column(String(32))
    unit = Column(String(16))
    normal_min = Column(DECIMAL(10, 4))
    normal_max = Column(DECIMAL(10, 4))
    warning_min = Column(DECIMAL(10, 4))
    warning_max = Column(DECIMAL(10, 4))
    critical_min = Column(DECIMAL(10, 4))
    critical_max = Column(DECIMAL(10, 4))
    baseline_value = Column(DECIMAL(10, 4))


class Alert(Base):
    __tablename__ = "alert"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id = Column(BigInteger, ForeignKey('equipment.id'), nullable=False)
    alert_type = Column(MysqlEnum('ANOMALY', 'RUL_WARNING', 'CRITICAL', 'SENSOR_FAILURE', 'MANUAL'), nullable=False)
    severity = Column(MysqlEnum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    feature_snapshot = Column(JSON)
    rul_hours = Column(Integer)
    risk_score = Column(DECIMAL(5, 2))
    status = Column(MysqlEnum('OPEN', 'ACKNOWLEDGED', 'ESCALATED', 'RESOLVED', 'IGNORED'), default='OPEN')
    agent_diagnosis = Column(Text)
    agent_rca = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class WorkOrder(Base):
    __tablename__ = "work_order"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_no = Column(String(64), unique=True, nullable=False)
    alert_id = Column(BigInteger, ForeignKey('alert.id'))
    equipment_id = Column(BigInteger, ForeignKey('equipment.id'), nullable=False)
    order_type = Column(MysqlEnum('PREVENTIVE', 'CORRECTIVE', 'EMERGENCY', 'SHUTDOWN_REQUEST'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    diagnosis = Column(Text)
    spare_parts = Column(JSON)
    status = Column(MysqlEnum('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'), default='DRAFT')
    priority = Column(MysqlEnum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'), default='MEDIUM')
    requires_human_approval = Column(Boolean, default=True)
    approval_policy = Column(String(32))
    created_by = Column(String(64), default='AGENT')
    created_at = Column(DateTime, server_default=func.now())


class MaintenanceManual(Base):
    __tablename__ = "maintenance_manual"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment_type = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    vendor = Column(String(128))
    version = Column(String(32))
    content_text = Column(Text)


class ManualChunk(Base):
    __tablename__ = "manual_chunk"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    manual_id = Column(BigInteger, ForeignKey('maintenance_manual.id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chapter = Column(String(64))
    section_title = Column(String(255))
    content = Column(Text, nullable=False)
    keywords = Column(String(512))


class AgentConversation(Base):
    __tablename__ = "agent_conversation"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    alert_id = Column(BigInteger, ForeignKey('alert.id'))
    role = Column(MysqlEnum('SYSTEM', 'USER', 'ASSISTANT', 'TOOL'), nullable=False)
    content = Column(Text)
    tool_name = Column(String(64))
    tool_args = Column(JSON)
    latency_ms = Column(Integer)
    model = Column(String(64))
    created_at = Column(DateTime, server_default=func.now())
