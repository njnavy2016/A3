# RCA 根因推演引擎 —— 基于特征→故障模式的规则匹配
from typing import Dict, List, Optional


# ============ 故障模式知识库 ============
# 每个故障模式定义：名称、描述、触发条件（特征→故障模式的 IF-THEN 规则）
# 这些规则与维修手册中的内容对应，供 LLM 做最终确认和补充
FAULT_KNOWLEDGE_BASE = [
    {
        "fault_mode": "轴承外圈点蚀",
        "chapter_reference": "3.2",
        "equipment_type": "WIND_GEARBOX",
        "triggers": [
            {"sensor": "VIBRATION", "condition": "spectral_sideband_ratio > 0.15"},
            {"sensor": "VIBRATION", "condition": "spectral_harmonic_ratio > 0.15"},
            {"sensor": "TEMPERATURE", "condition": "degradation_index > 30 AND trend_direction == 'up'"},
        ],
        "description": "轴承外圈滚道出现早期点蚀，BPFO 边频带能量比升高",
        "recommended_action": "缩短润滑油更换周期 50%，增加振动监测频率至每 4 小时一次；若振动 RMS 超过 4.5 mm/s，在下一个维护窗口更换轴承",
        "likelihood_factors": {
            "spectral_sideband_ratio > 0.15": 0.4,
            "spectral_harmonic_ratio > 0.15": 0.3,
            "TEMPERATURE trend up": 0.2,
            "overall degradation > 30%": 0.1,
        },
    },
    {
        "fault_mode": "齿轮轮齿磨损",
        "chapter_reference": "4.1",
        "equipment_type": "WIND_GEARBOX",
        "triggers": [
            {"sensor": "VIBRATION", "condition": "spectral_harmonic_ratio > 0.3"},
            {"sensor": "CURRENT", "condition": "degradation_index > 20"},
        ],
        "description": "齿轮点蚀、剥落或断齿导致冲击调制响应，GMF 谐波能量升高",
        "recommended_action": "安排内窥镜检查；若确认断齿，立即申请停机更换；若仅为点蚀，缩短监测周期",
        "likelihood_factors": {
            "spectral_harmonic_ratio > 0.3": 0.5,
            "CURRENT degradation > 20%": 0.3,
            "multiple VIBRATION sensors affected": 0.2,
        },
    },
    {
        "fault_mode": "润滑油滤油器堵塞",
        "chapter_reference": "6.5",
        "equipment_type": "WIND_GEARBOX",
        "triggers": [
            {"sensor": "OIL_PRESSURE", "condition": "degradation_index > 30 AND trend_direction == 'down'"},
            {"sensor": "OIL_PRESSURE", "condition": "current_mean < 2.5"},
        ],
        "description": "滤油器堵塞导致润滑油压力下降和波动",
        "recommended_action": "检查滤油器压差；若压差 > 1.2 bar，通过旁路阀临时切换，尽快安排更换滤芯",
        "likelihood_factors": {
            "OIL_PRESSURE trend down": 0.5,
            "OIL_PRESSURE absolute low": 0.3,
            "no TEMP degradation": 0.2,
        },
    },
    {
        "fault_mode": "轴承保持架磨损",
        "chapter_reference": "2.1",
        "equipment_type": "WIND_GEARBOX",
        "triggers": [
            {"sensor": "VIBRATION", "condition": "outlier_ratio > 0.02"},
            {"sensor": "VIBRATION", "condition": "spectral_sideband_ratio > 0.08 AND < 0.15"},
        ],
        "description": "保持架磨损导致振动中有间歇型异常冲击，但整体边频带能量比尚未很高",
        "recommended_action": "密切监测；若边频带能量比继续上升超过 0.15，按轴承点蚀处理",
        "likelihood_factors": {
            "VIBRATION outlier > 2%": 0.5,
            "sideband_ratio borderline": 0.3,
            "degradation moderate": 0.2,
        },
    },
    {
        "fault_mode": "正常退化（无需干预）",
        "chapter_reference": None,
        "equipment_type": "WIND_GEARBOX",
        "triggers": [
            {"sensor": "ANY", "condition": "all degradation_index < 20"},
        ],
        "description": "设备整体状态良好，仅有正常波动",
        "recommended_action": "按常规维护周期执行，保持现有监测频率",
        "likelihood_factors": {
            "all sensors healthy": 1.0,
        },
    },
]


class RCAEngine:
    """
    基于规则 + 置信度计算的根因分析引擎。
    LLM 将根据此处的候选根因 + 维修手册 + 历史工单，做最终裁决。
    """
    
    def analyze(
        self,
        equipment_type: str,
        sensor_features: Dict[str, Dict],
        anomaly_result: Dict,
        manual_chunks: List[Dict] = None,
        historical_cases: List[Dict] = None,
    ) -> Dict:
        """
        运行 RCA 规则匹配。
        返回: {
            "root_causes": [
                {
                    "fault_mode": str,
                    "confidence": float,   # 规则计算的置信度 0-1
                    "matched_rules": [str],
                    "evidence": [str],
                    "recommended_action": str,
                    "chapter_reference": str,
                }
            ],
            "top_cause": str or None,
            "need_llm_verification": bool,   # 是否需要 LLM 做最终裁决
        }
        """
        candidates = []
        
        for pattern in FAULT_KNOWLEDGE_BASE:
            if equipment_type != pattern["equipment_type"]:
                continue
            
            score = 0.0
            matched_rules = []
            evidence = []
            
            for trigger in pattern["triggers"]:
                sensor_type = trigger["sensor"]
                condition = trigger["condition"]
                
                # 解析条件（简化版：关键词匹配）
                match, detail = self._evaluate_condition(
                    sensor_type, condition, sensor_features
                )
                if match:
                    # 权重根据 likelihood_factors 动态计算
                    weight = 0.3  # 默认权重
                    for factor_text, factor_weight in pattern.get("likelihood_factors", {}).items():
                        if factor_text in condition or condition in factor_text:
                            weight = factor_weight
                            break
                    score += weight
                    matched_rules.append(f"{sensor_type}: {condition}")
                    evidence.append(detail)
            
            if score > 0.0:
                # 检查是否完全匹配所有（核心触发规则）
                confidence = min(1.0, score)
                
                candidates.append({
                    "fault_mode": pattern["fault_mode"],
                    "confidence": round(confidence, 3),
                    "matched_rules": matched_rules,
                    "evidence": evidence,
                    "recommended_action": pattern["recommended_action"],
                    "chapter_reference": pattern.get("chapter_reference"),
                })
        
        # 按置信度排序
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        
        top_cause = candidates[0] if candidates else None
        
        # 判断是否需要 LLM 验证
        need_llm = (
            len(candidates) >= 2 and candidates[0]["confidence"] < 0.7
            or anomaly_result.get("level") in ("MEDIUM", "HIGH", "CRITICAL")
        )
        
        return {
            "root_causes": candidates,
            "top_cause": top_cause,
            "need_llm_verification": need_llm,
            "evidence_summary": self._summarize_evidence(sensor_features),
        }
    
    def _evaluate_condition(
        self,
        sensor_type: str,
        condition: str,
        features: Dict[str, Dict],
    ) -> tuple:
        """
        评估单个条件。
        返回 (是否匹配, 详情描述)
        """
        # 从所有传感器中找匹配类型的
        matching_sensors = {
            code: f for code, f in features.items()
            if sensor_type == "ANY" or code.startswith(sensor_type)
        }
        
        if not matching_sensors:
            # 特殊：检查全局退化
            if sensor_type == "ANY":
                avg_deg = sum(f.get("degradation_index", 0) for f in features.values()) / max(len(features), 1)
                if "all degradation_index < 20" in condition:
                    if avg_deg < 20:
                        return True, f"所有传感器平均退化指数 {avg_deg:.1f}% < 20%"
                    return False, ""
            return False, ""
        
        any_match = False
        details = []
        
        for sensor_code, feat in matching_sensors.items():
            result = self._parse_single_condition(condition, feat, sensor_code)
            if result:
                any_match = True
                details.append(result)
        
        return any_match, "; ".join(details) if any_match else ""
    
    def _parse_single_condition(
        self, condition: str, feat: Dict, sensor_code: str
    ) -> Optional[str]:
        """
        解析类似 "degradation_index > 30" 的条件。
        """
        import re
        
        # 提取字段名、比较符、数值
        m = re.search(r"(\w+(?:_\w+)*)\s*(>|<|>=|<=|==)\s*([\d.]+)", condition)
        if not m:
            return None
        
        field, op, threshold_str = m.group(1), m.group(2), m.group(3)
        
        # 特殊处理 AND
        if "AND" in condition.upper():
            parts = [p.strip() for p in re.split(r"\s+AND\s+", condition, flags=re.IGNORECASE)]
            results = []
            for part in parts:
                sub_result = self._parse_single_condition(part, feat, sensor_code)
                results.append(sub_result)
            if all(results):
                return f"{sensor_code}: {' AND '.join(results)}"
            return None
        
        value = feat.get(field)
        if value is None:
            return None
        
        threshold = float(threshold_str)
        
        match = False
        if op == ">":
            match = value > threshold
        elif op == "<":
            match = value < threshold
        elif op == ">=":
            match = value >= threshold
        elif op == "<=":
            match = value <= threshold
        
        if match:
            return f"{sensor_code}.{field}={value} {op} {threshold}"
        return None
    
    def _summarize_evidence(self, features: Dict) -> str:
        lines = []
        for code, feat in features.items():
            deg = feat.get("degradation_index", 0)
            trend = feat.get("trend_direction", "stable")
            lines.append(f"  - {code}: 退化 {deg}%, 趋势 {trend}")
        return "\n".join(lines)
