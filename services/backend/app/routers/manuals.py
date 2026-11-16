# Manuals 路由
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from .. import models

router = APIRouter()


@router.get("")
def list_manuals(
    equipment_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.MaintenanceManual)
    if equipment_type:
        query = query.filter(models.MaintenanceManual.equipment_type == equipment_type)
    manuals = query.all()
    
    result = []
    for m in manuals:
        chunks = db.query(models.ManualChunk).filter(
            models.ManualChunk.manual_id == m.id
        ).order_by(models.ManualChunk.chunk_index).all()
        
        result.append({
            "id": m.id,
            "title": m.title,
            "vendor": m.vendor,
            "version": m.version,
            "equipment_type": m.equipment_type,
            "chunk_count": len(chunks),
            "chunks": [
                {
                    "id": c.id,
                    "chapter": c.chapter,
                    "section_title": c.section_title,
                    "content": c.content,
                    "keywords": c.keywords,
                }
                for c in chunks
            ],
        })
    
    return result


@router.get("/chunks/search")
def search_chunks(
    equipment_type: str,
    keyword: str,
    top_k: int = 3,
    db: Session = Depends(get_db),
):
    """简单关键词检索（实际 RAG 在 Agent 侧）"""
    chunks = db.query(models.ManualChunk).join(
        models.MaintenanceManual, models.MaintenanceManual.id == models.ManualChunk.manual_id
    ).filter(
        models.MaintenanceManual.equipment_type == equipment_type,
        models.ManualChunk.content.like(f"%{keyword}%"),
    ).limit(top_k).all()
    
    return [
        {
            "chapter": c.chapter,
            "section_title": c.section_title,
            "content": c.content,
        }
        for c in chunks
    ]
