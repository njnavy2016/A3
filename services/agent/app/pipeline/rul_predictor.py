# RUL 预估 —— 基于退化趋势的剩余使用寿命估算
from typing import Dict, Optional
import math


class RULPredictor:
    """
    基于退化指数和趋势斜率的简化 RUL 预估。
    (实际项目可接入专门的退化模型，这里做工程化简化)
    """
    
    # 不同设备的典型退化阈值（超过此值视为失效）
    FAILURE_THRESHOLDS = {
        "WIND_GEARBOX": {
            "VIBRATION": 4.5,       # mm/s
            "TEMPERATURE": 75.0,    # ℃
            "OIL_PRESSURE": 1.5,    # bar（下限）
        },
        "GENERIC": {
            "default": 1.5,
        }
    }
    
    def predict(
        self,
        equipment_type: str,
        sensor_features: Dict[str, Dict],
        interval_minutes: int = 60,
    ) -> Dict:
        """
        返回预估的 RUL（小时）及置信度。
        """
        worst_rul = None
        contributing_sensors = []
        
        thresholds = self.FAILURE_THRESHOLDS.get(equipment_type, self.FAILURE_THRESHOLDS["GENERIC"])
        
        for sensor_code, features in sensor_features.items():
            # 只看有趋势的传感器
            trend = features.get("trend_direction", "stable")
            if trend == "stable" or trend == "down":
                continue
            
            sensor_type = sensor_code.split("_")[0]
            threshold = thresholds.get(sensor_type, thresholds.get("default", float("inf")))
            
            # 当前值
            current = features.get("last_val") or features.get("mean")
            if current is None:
                continue
            
            # 斜率（per sample）→ 转 per hour
            slope_per_sample = features.get("slope_per_sample", 0)
            samples_per_hour = 60.0 / interval_minutes
            slope_per_hour = slope_per_sample * samples_per_hour
            
            if slope_per_hour <= 0:
                continue
            
            # 计算 RUL
            # vibration/temperature: 阈值 - current 为剩余裕量
            # oil_pressure: current - 临界下限
            if sensor_type == "OIL_PRESSURE":
                # 油压低是坏的，斜率为负
                critical_lower = 1.5
                margin = current - critical_lower
                effective_slope = abs(slope_per_hour)
            else:
                critical_upper = threshold
                margin = critical_upper - current
                effective_slope = slope_per_hour
            
            if margin <= 0:
                # 已经超过临界值
                rul_hours = 0
                confidence = 0.3
            else:
                rul_hours = margin / max(effective_slope, 1e-6)
                # 限制在合理范围
                rul_hours = max(0, min(rul_hours, 8760))  # 最多一年
                confidence = self._calc_confidence(features)
            
            contributing_sensors.append({
                "sensor": sensor_code,
                "current_value": current,
                "slope_per_hour": effective_slope,
                "failure_threshold": threshold,
                "rul_hours": round(rul_hours, 1),
                "confidence": confidence,
            })
            
            if worst_rul is None or rul_hours < worst_rul:
                worst_rul = rul_hours
        
        if worst_rul is None:
            return {
                "rul_hours": 2000,  # 没有退化趋势 → 给个安全值
                "rul_status": "stable",
                "confidence": 0.4,
                "contributing_sensors": contributing_sensors,
                "message": "未检测到明显退化趋势，RUL 估算基于稳定假设",
            }
        
        return {
            "rul_hours": round(worst_rul, 1),
            "rul_status": "critical" if worst_rul < 72 else
                         "warn" if worst_rul < 240 else
                         "monitor",
            "confidence": self._overall_confidence(contributing_sensors),
            "contributing_sensors": contributing_sensors,
            "message": self._rul_message(worst_rul),
        }
    
    def _calc_confidence(self, features: Dict) -> float:
        """根据数据质量估算置信度"""
        missing = features.get("missing_ratio", 0)
        confidence = 0.8
        confidence -= missing * 2  # 缺失越多越不可信
        if features.get("total_points", 999) < 60:
            confidence -= 0.2
        return max(0.1, min(0.95, confidence))
    
    def _overall_confidence(self, sensors: list) -> float:
        if not sensors:
            return 0.4
        confs = [s["confidence"] for s in sensors]
        return round(sum(confs) / len(confs), 2)
    
    def _rul_message(self, hours: float) -> str:
        if hours < 24:
            return "⚠️ 非常紧急：预计 24 小时内可能失效，建议立即停机检查"
        elif hours < 72:
            return "⚠️ 紧急：预计 72 小时内可能失效，本周内必须安排检修"
        elif hours < 168:  # 1周
            return "🔴 高优先级：预计一周内可能失效，尽快安排维护窗口"
        elif hours < 720:  # 1月
            return "🟡 中优先级：一个月内可能失效，建议缩短监测周期"
        else:
            return "🟢 健康状态良好：RUL 充足，按常规维护周期执行"
