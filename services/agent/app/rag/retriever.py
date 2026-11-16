# 维修手册检索器 —— 从 MySQL 检索相关手册章节
from typing import List, Dict, Optional
import re
from sqlalchemy.orm import Session
from .. import models


class ManualRetriever:
    """
    基于关键词匹配的手册章节检索（第一版）。
    后续可升级为向量检索 / Embedding。
    """
    
    # 故障关键词映射
    FAULT_KEYWORD_MAP = {
        "轴承": ["轴承", "bearing", "BPFO", "BPFI", "点蚀", "保持架", "外圈"],
        "齿轮": ["齿轮", "齿面", "轮齿", "点蚀", "剥落", "断齿", "GMF", "啮合"],
        "润滑油": ["润滑", "油", "oil", "油压", "滤油器", "油温", "泵"],
        "振动": ["振动", "vibration", "频谱", "边频带", "冲击", "调制"],
        "温度": ["温度", "temperature", "热", "温升", "过热"],
        "电流": ["电流", "current", "谐波"],
        "密封": ["密封", "漏油", "泄漏", "密封件"],
        "内窥镜": ["内窥镜", "检查"],
    }
    
    def retrieve(
        self,
        db: Session,
        equipment_type: str,
        query_keywords: List[str],
        top_k: int = 5,
    ) -> List[Dict]:
        """
        检索维修手册中与关键词最相关的章节 chunk。
        """
        # 获取该设备类型的所有手册章节
        chunks = db.query(models.ManualChunk).join(
            models.MaintenanceManual,
            models.MaintenanceManual.id == models.ManualChunk.manual_id
        ).filter(
            models.MaintenanceManual.equipment_type == equipment_type
        ).all()
        
        if not chunks:
            return []
        
        # 评分排序
        scored = []
        for chunk in chunks:
            score = self._score_chunk(chunk.content, query_keywords, chunk.keywords)
            if score > 0:
                scored.append({
                    "chapter": chunk.chapter,
                    "section_title": chunk.section_title,
                    "content": chunk.content,
                    "keywords": chunk.keywords,
                    "score": score,
                })
        
        # 同时返回该设备类型的全部手册元信息
        manuals = db.query(models.MaintenanceManual).filter(
            models.MaintenanceManual.equipment_type == equipment_type
        ).all()
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        return scored[:top_k]
    
    def _score_chunk(
        self,
        content: str,
        query_keywords: List[str],
        chunk_keywords: Optional[str],
    ) -> float:
        """简单的关键词命中评分"""
        score = 0
        content_lower = content.lower()
        
        # 直接关键词匹配
        for kw in query_keywords:
            if kw and kw.lower() in content_lower:
                score += 2.0
        
        # 扩展关键词映射
        expanded = set(query_keywords)
        for category, related in self.FAULT_KEYWORD_MAP.items():
            if any(k in expanded for k in related) or any(k in expanded for k in [category]):
                for rel_kw in related:
                    if rel_kw.lower() in content_lower:
                        score += 1.0
        
        # chunk 自带的关键词字段命中
        if chunk_keywords:
            for kw in query_keywords:
                if kw and kw.lower() in chunk_keywords.lower():
                    score += 3.0
        
        return score
    
    def format_for_llm(self, chunks: List[Dict]) -> str:
        """格式化为 LLM Prompt 片段"""
        if not chunks:
            return "（未检索到相关维修手册内容）"
        
        lines = ["## 维修手册相关章节\n"]
        for i, chunk in enumerate(chunks, 1):
            chapter = chunk.get("chapter", "")
            title = chunk.get("section_title", "")
            content = chunk.get("content", "")
            lines.append(f"### [{i}] 章节 {chapter} - {title}")
            lines.append(content.strip())
            lines.append("")
        
        return "\n".join(lines)
