# Agent 路由 —— 转发到 Agent 服务
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import httpx
import os

router = APIRouter()

AGENT_URL = os.environ.get("AGENT_URL", "http://agent:8100")


@router.post("/trigger-analysis/{alert_id}")
async def trigger_agent_analysis(alert_id: int):
    """
    触发 Agent 对某个告警进行分析。
    实际推理在 Agent 服务完成，Backend 只做转发。
    """
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                f"{AGENT_URL}/api/v1/analyze/{alert_id}",
                json={"triggered_by": "backend"},
            )
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Agent 服务不可用: {e}")


@router.post("/chat")
async def agent_chat(payload: dict):
    """前端直接与 Agent 对话（通过 Backend 转发）"""
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                f"{AGENT_URL}/api/v1/chat",
                json=payload,
            )
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Agent 服务不可用: {e}")
