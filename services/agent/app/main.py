# Agent 主入口（FastAPI）—— 整合全部 Pipeline
import os
import sys
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

import redis.asyncio as aioredis
import httpx
import numpy as np
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import Base, Equipment, Sensor, Alert, WorkOrder, MaintenanceManual, ManualChunk, AgentConversation
from pipeline.feature_extractor import FeatureExtractor, format_features_for_llm
from pipeline.anomaly_detector import AnomalyDetector
from pipeline.rca_engine import RCAEngine
from pipeline.rul_predictor import RULPredictor
from pipeline.approval_gate import ApprovalGate
from rag.retriever import ManualRetriever
from llm_client import llm_client
from prompts.templates import SYSTEM_PROMPT, RCA_ANALYSIS_PROMPT, build_prompt


# ============================================================
# 数据库 & Redis 初始化
# ============================================================
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
redis_pool = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# FastAPI 应用
# ============================================================
app = FastAPI(
    title="PdM Agent Service",
    version="1.0.0",
    description="预测性维护智能体核心服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipeline 组件实例
extractor = None
detector = AnomalyDetector()
rca_engine = RCAEngine()
rul_predictor = RULPredictor()
approval_gate = ApprovalGate()
manual_retriever = ManualRetriever()


# ============================================================
# 启动/关闭事件
# ============================================================
@app.on_event("startup")
async def on_startup():
    global redis_pool
    redis_pool = await aioredis.from_url(
        config.REDIS_URL, decode_responses=True
    )
    await redis_pool.ping()
    print("[Agent] Redis 连接成功")
    print(f"[Agent] LLM 配置: model={config.LLM_MODEL}")
    print("[Agent] 服务启动完成")


@app.on_event("shutdown")
async def on_shutdown():
    if redis_pool:
        await redis_pool.close()
    await llm_client.close()


# ============================================================
# 基础端点
# ============================================================
@app.get("/health")
async def health_check():
    redis_ok = False
    if redis_pool:
        try:
            redis_ok = await redis_pool.ping()
        except Exception:
            pass
    return {
        "status": "ok",
        "service": "agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": redis_ok,
        "llm_configured": bool(config.LLM_API_KEY),
    }


# ============================================================
# 核心：分析接口
# ============================================================
class AnalyzeRequest(BaseModel):
    equipment_code: Optional[str] = None
    equipment_id: Optional[int] = None
    alert_id: Optional[int] = None
    triggered_by: str = "MANUAL"
    force_llm: bool = False


@app.post("/api/v1/analyze")
async def analyze_equipment(req: AnalyzeRequest):
    """
    完整分析流水线：
    Redis 原始数据 → 特征提取 → 异常检测 → RCA → RUL → (LLM) → 告警/工单
    """
    db = SessionLocal()
    session_id = str(uuid.uuid4())
    
    try:
        # 1. 定位设备
        equipment = None
        if req.equipment_id:
            equipment = db.query(Equipment).filter(Equipment.id == req.equipment_id).first()
        elif req.equipment_code:
            equipment = db.query(Equipment).filter(Equipment.equipment_code == req.equipment_code).first()
        elif req.alert_id:
            alert = db.query(Alert).filter(Alert.id == req.alert_id).first()
            if alert:
                equipment = db.query(Equipment).filter(Equipment.id == alert.equipment_id).first()
        
        if not equipment:
            raise HTTPException(404, "设备不存在")
        
        print(f"[Agent] 开始分析 {equipment.equipment_code} ({equipment.equipment_type})")
        
        # 2. 获取该设备所有传感器
        sensors = db.query(Sensor).filter(Sensor.equipment_id == equipment.id).all()
        if not sensors:
            raise HTTPException(400, "该设备无传感器配置")
        
        # 3. 从 Redis 拉取每个传感器的原始数据（最近 360 分钟）
        sensor_raw_data = {}
        for sensor in sensors:
            key = f"ts:{equipment.equipment_code}:{sensor.sensor_code}"
            raw = await redis_pool.zrange(key, -360, -1)
            if raw:
                values = []
                for item in raw:
                    try:
                        data = json.loads(item)
                        values.append(float(data["v"]))
                    except Exception:
                        values.append(float("nan"))
                sensor_raw_data[sensor.sensor_code] = values
        
        if not sensor_raw_data:
            return {
                "status": "no_data",
                "message": "Redis 中暂无传感器数据，请确认 Sensor Simulator 是否正常运行",
                "equipment_code": equipment.equipment_code,
            }
        
        print(f"[Agent] 拉取到 {len(sensor_raw_data)} 个传感器的原始数据")
        
        # 4. 特征提取（核心——将高频数据压缩为紧凑摘要）
        sensor_features = {}
        for sensor_code, raw in sensor_raw_data.items():
            # 找到对应的 Sensor 元数据
            sensor_meta = next((s for s in sensors if s.sensor_code == sensor_code), None)
            if not sensor_meta:
                continue
            
            extractor = FeatureExtractor(
                baseline=float(sensor_meta.baseline_value or 0),
                normal_range=(
                    float(sensor_meta.normal_min or 0),
                    float(sensor_meta.normal_max or float("inf")),
                ),
                sensor_type=sensor_meta.sensor_type,
            )
            features = extractor.extract(raw)
            sensor_features[sensor_code] = features
        
        # 5. 异常检测
        sensor_anomalies = {}
        for code, feat in sensor_features.items():
            sensor_anomalies[code] = detector.detect(feat)
        overall_anomaly = detector.aggregate_equipment_anomaly(sensor_anomalies)
        
        print(f"[Agent] 异常评估: {overall_anomaly['level']} (score={overall_anomaly['score']})")
        
        # 6. RUL 预估
        rul_result = rul_predictor.predict(
            equipment.equipment_type, sensor_features, interval_minutes=1
        )
        
        # 7. 规则引擎 RCA
        rca_result = rca_engine.analyze(
            equipment.equipment_type, sensor_features, overall_anomaly
        )
        
        # 8. RAG 检索维修手册
        query_keywords = []
        if overall_anomaly["affected_sensors"]:
            for s in overall_anomaly["affected_sensors"]:
                code = s["sensor"].lower()
                if "vib" in code: query_keywords.extend(["振动", "轴承", "齿轮", "BPFO", "GMF"])
                if "temp" in code: query_keywords.extend(["温度", "热", "轴承"])
                if "oil" in code: query_keywords.extend(["油", "油压", "滤油器"])
                if "curr" in code: query_keywords.extend(["电流", "谐波"])
        
        manual_chunks = manual_retriever.retrieve(
            db, equipment.equipment_type, query_keywords, top_k=5
        )
        manual_context = manual_retriever.format_for_llm(manual_chunks)
        
        # 9. LLM 深度推理（如果配置了 API Key 或强制）
        llm_analysis = None
        use_llm = (config.LLM_API_KEY and (rca_result["need_llm_verification"] or req.force_llm or overall_anomaly["level"] != "NONE"))
        
        if use_llm:
            llm_analysis = await _run_llm_analysis(
                session_id, equipment, sensor_features, overall_anomaly,
                rca_result, manual_chunks, rul_result, db
            )
        
        # 10. 综合结果
        risk_score = min(100, overall_anomaly["score"] + (rul_result["confidence"] * 10 if rul_result["rul_hours"] < 720 else 0))
        
        # 11. 如果异常显著，创建告警
        alert_id = None
        if overall_anomaly["level"] in ("MEDIUM", "HIGH", "CRITICAL"):
            alert = Alert(
                equipment_id=equipment.id,
                alert_type="ANOMALY",
                severity=overall_anomaly["level"],
                title=f"{equipment.equipment_code} 检测到 {overall_anomaly['level']} 级异常",
                description=f"影响传感器 {overall_anomaly['affected_count']}/{overall_anomaly['total_sensors']}，风险评分 {risk_score:.1f}",
                feature_snapshot=sensor_features,
                rul_hours=rul_result.get("rul_hours"),
                risk_score=risk_score,
                agent_diagnosis=(llm_analysis or {}).get("root_cause") or
                                  (rca_result["top_cause"]["fault_mode"] if rca_result["top_cause"] else "未知"),
                agent_rca=json.dumps(rca_result["root_causes"], ensure_ascii=False),
            )
            db.add(alert)
            db.flush()
            alert_id = alert.id
            
            # 更新健康分数
            new_health = max(0, min(100, 100 - risk_score * 0.5))
            equipment.health_score = new_health
            if overall_anomaly["level"] == "CRITICAL":
                equipment.status = "CRITICAL"
            elif overall_anomaly["level"] == "HIGH":
                equipment.status = "MAINTENANCE"
            db.commit()
            
            print(f"[Agent] 告警已创建: Alert #{alert_id}")
        
        # 12. 如果 RCA 或 LLM 建议工单，触发 HITL 拦截
        work_order_result = None
        llm_wo_suggestion = (llm_analysis or {}).get("work_order_suggestion")
        if llm_wo_suggestion:
            work_order_result = await _create_hitl_work_order(
                session_id, equipment, alert_id, llm_wo_suggestion, overall_anomaly, db
            )
        
        return {
            "status": "ok",
            "session_id": session_id,
            "equipment_code": equipment.equipment_code,
            "anomaly_level": overall_anomaly["level"],
            "anomaly_score": overall_anomaly["score"],
            "rul": rul_result,
            "rca": rca_result,
            "llm_used": bool(llm_analysis),
            "llm_analysis": llm_analysis,
            "alert_created": alert_id is not None,
            "alert_id": alert_id,
            "work_order": work_order_result,
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e), "session_id": session_id}
    finally:
        db.close()


# ============================================================
# 内部：LLM 完整分析
# ============================================================
async def _run_llm_analysis(
    session_id: str,
    equipment: Equipment,
    sensor_features: Dict,
    overall_anomaly: Dict,
    rca_result: Dict,
    manual_chunks: List[Dict],
    rul_result: Dict,
    db,
) -> Dict:
    """执行 LLM 深度分析，返回结构化结果"""
    
    # 格式化特征
    features_text = "\n\n".join(
        format_features_for_llm(code, feat)
        for code, feat in sensor_features.items()
    )
    
    # 格式化 RCA 规则引擎结果
    rule_engine_text = ""
    if rca_result["root_causes"]:
        lines = ["规则引擎匹配的候选根因："]
        for i, rc in enumerate(rca_result["root_causes"], 1):
            lines.append(f"  [{i}] {rc['fault_mode']} (置信度 {rc['confidence']})")
            lines.append(f"      匹配规则: {', '.join(rc['matched_rules'])}")
            if rc.get("chapter_reference"):
                lines.append(f"      参考章节: {rc['chapter_reference']}")
        rule_engine_text = "\n".join(lines)
    else:
        rule_engine_text = "规则引擎未匹配到明确故障模式，可能为复合退化或正常波动。"
    
    manual_text = manual_retriever.format_for_llm(manual_chunks)
    historical_text = "（暂无足够历史案例）"  # 可扩展
    
    # 组装 Prompt
    prompt = build_prompt(
        RCA_ANALYSIS_PROMPT,
        equipment_code=equipment.equipment_code,
        equipment_type=equipment.equipment_type,
        health_score=float(equipment.health_score or 100),
        equipment_status=equipment.status,
        sensor_features_formatted=features_text,
        rule_engine_result=rule_engine_text,
        manual_chunks_formatted=manual_text,
        historical_cases_formatted=historical_text,
    )
    
    # 保存系统消息
    db.add(AgentConversation(
        session_id=session_id, alert_id=None, role="SYSTEM",
        content=SYSTEM_PROMPT[:500], model=config.LLM_MODEL,
    ))
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    
    print(f"[Agent] 调用 LLM ({config.LLM_MODEL}) 进行 RCA 分析...")
    start = datetime.now()
    
    response = await llm_client.chat(messages, temperature=0.3, max_tokens=6000)
    
    latency = int((datetime.now() - start).total_seconds() * 1000)
    print(f"[Agent] LLM 响应完成，耗时 {latency}ms")
    
    # 保存对话
    db.add(AgentConversation(
        session_id=session_id, alert_id=None, role="USER",
        content=prompt[:2000], model=config.LLM_MODEL, latency_ms=latency,
    ))
    db.add(AgentConversation(
        session_id=session_id, alert_id=None, role="ASSISTANT",
        content=response[:5000], model=config.LLM_MODEL, latency_ms=latency,
    ))
    db.commit()
    
    return {
        "root_cause": rca_result["top_cause"]["fault_mode"] if rca_result["top_cause"] else None,
        "full_response": response,
        "latency_ms": latency,
        "work_order_suggestion": _extract_work_order_json(response),
    }


def _extract_work_order_json(text: str) -> Optional[Dict]:
    """从 LLM 响应中提取工单 JSON 建议"""
    import re
    # 找 ```json ... ``` 块
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if not m:
        m = re.search(r'\{[^{}]*"order_type"[^{}]*\}', text)
    
    if m:
        try:
            return json.loads(m.group(1) if m.groups() else m.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


# ============================================================
# 内部：创建 HITL 工单（拦截器）
# ============================================================
async def _create_hitl_work_order(
    session_id: str,
    equipment: Equipment,
    alert_id: Optional[int],
    suggestion: Dict,
    anomaly_result: Dict,
    db,
) -> Dict:
    """
    Agent 生成工单建议 → ApprovalGate 拦截 → 创建待审批工单
    """
    # 1. 确定动作类型
    action_map = {
        "SHUTDOWN_REQUEST": "create_work_order_shutdown",
        "EMERGENCY": "create_work_order_emergency",
        "CORRECTIVE": "create_work_order_corrective",
        "PREVENTIVE": "create_work_order_preventive",
    }
    action_type = action_map.get(suggestion.get("order_type", ""), "create_work_order_preventive")
    
    # 2. 审批评估
    decision = approval_gate.evaluate(
        action=action_type,
        context={
            "risk_level": anomaly_result["level"],
            "equipment_type": equipment.equipment_type,
            "value": sum(
                (p.get("unit_price", 0) * p.get("qty", 1))
                for p in (suggestion.get("spare_parts") or [])
            ),
        },
    )
    
    # 3. 生成工单编号
    import uuid
    now = datetime.now()
    order_no = f"WO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # 4. 创建工单（PENDING_APPROVAL 状态，等待人工审批）
    wo = WorkOrder(
        order_no=order_no,
        alert_id=alert_id,
        equipment_id=equipment.id,
        order_type=suggestion.get("order_type", "CORRECTIVE"),
        title=suggestion.get("title", f"设备 {equipment.equipment_code} 维护工单"),
        description=suggestion.get("description", ""),
        diagnosis=suggestion.get("diagnosis", ""),
        spare_parts=suggestion.get("spare_parts", []),
        status="PENDING_APPROVAL" if decision.requires_approval else "APPROVED",
        priority=suggestion.get("priority", "MEDIUM"),
        requires_human_approval=decision.requires_approval,
        approval_policy=decision.policy_tag,
        created_by="AGENT",
    )
    db.add(wo)
    db.commit()
    
    result = {
        "order_no": order_no,
        "work_order_id": wo.id,
        "status": wo.status,
        "approval_decision": {
            "requires_approval": decision.requires_approval,
            "approver_role": decision.approver_role,
            "reason": decision.reason,
            "policy_tag": decision.policy_tag,
        },
    }
    
    if decision.requires_approval:
        print(f"[Agent] ⚠️ 工单已创建并被 HITL 拦截: {order_no} → 需要 {decision.approver_role} 审批")
    else:
        print(f"[Agent] 工单自动通过: {order_no}")
    
    return result


# ============================================================
# Chat 接口
# ============================================================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    equipment_id: Optional[int] = None


@app.post("/api/v1/chat")
async def agent_chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    db = SessionLocal()
    
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ]
        
        response = await llm_client.chat(messages)
        
        db.add(AgentConversation(
            session_id=session_id, role="USER",
            content=req.message, model=config.LLM_MODEL,
        ))
        db.add(AgentConversation(
            session_id=session_id, role="ASSISTANT",
            content=response[:5000], model=config.LLM_MODEL,
        ))
        db.commit()
        
        return {
            "session_id": session_id,
            "response": response,
            "model": config.LLM_MODEL,
        }
    finally:
        db.close()


# ============================================================
# 测试接口：注入故障
# ============================================================
class FaultInjectRequest(BaseModel):
    equipment_code: str = "WT-GEAR-003"
    fault_type: str = "bearing_pitting"   # bearing_pitting / oil_leak / gear_wear


@app.post("/api/v1/test/inject-fault")
async def inject_fault(req: FaultInjectRequest):
    """
    测试接口：触发对某设备的完整分析。
    (实际故障注入在 Sensor Simulator 侧通过环境变量控制)
    """
    # 直接触发分析
    db = SessionLocal()
    equipment = db.query(Equipment).filter(
        Equipment.equipment_code == req.equipment_code
    ).first()
    db.close()
    
    if not equipment:
        raise HTTPException(404, "设备不存在")
    
    result = await analyze_equipment(AnalyzeRequest(
        equipment_code=req.equipment_code,
        force_llm=True,
    ))
    
    return {
        "fault_injected_type": req.fault_type,
        "analysis_result": result,
        "tip": "故障模拟需要在 Sensor Simulator 中设置 SIM_MODE=fault 或触发 API",
    }


# ============================================================
# 对话历史查询
# ============================================================
@app.get("/api/v1/conversations/{session_id}")
async def get_conversation(session_id: str):
    db = SessionLocal()
    try:
        convs = db.query(AgentConversation).filter(
            AgentConversation.session_id == session_id
        ).order_by(AgentConversation.created_at.asc()).all()
        
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": c.role,
                    "content": c.content[:2000],
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "model": c.model,
                    "latency_ms": c.latency_ms,
                }
                for c in convs
            ],
        }
    finally:
        db.close()
