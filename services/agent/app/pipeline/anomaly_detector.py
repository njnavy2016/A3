# 异常检测器（基于统计阈值）
from typing import Dict, List, Optional
import numpy as np


class AnomalyDetector:
    """多策略异常检测"""
    
    def detect(self, sensor_features: Dict, sensor_meta: Dict = None) -> Dict:
        """
        综合评估某个传感器的异常等级。
        返回: {
            "level": "NONE / LOW / MEDIUM / HIGH / CRITICAL",
            "reasons": [str, ...],
            "score": float  # 0-100
        }
        """
        reasons = []
        score = 0
        
        # 策略 1: 退化指数
        deg_idx = sensor_features.get("degradation_index", 0)
        if deg_idx > 70:
            score += 40
            reasons.append(f"退化指数 {deg_idx}% 过高")
        elif deg_idx > 40:
            score += 25
            reasons.append(f"退化指数 {deg_idx}% 偏高")
        elif deg_idx > 20:
            score += 10
            reasons.append(f"退化指数 {deg_idx}% 有上升趋势")
        
        # 策略 2: 阈值违规
        violations = sensor_features.get("threshold_violations", 0)
        ratio = sensor_features.get("threshold_violation_ratio", 0)
        if violations > 10 or ratio > 0.05:
            score += 35
            reasons.append(f"阈值违规 {violations} 次，超过 5%")
        elif violations > 3:
            score += 20
            reasons.append(f"阈值违规 {violations} 次")
        elif violations > 0:
            score += 10
            reasons.append(f"阈值违规 {violations} 次（少量）")
        
        # 策略 3: 趋势（非稳定）
        trend = sensor_features.get("trend_direction", "stable")
        health = sensor_features.get("health_status", "HEALTHY")
        if health in ("WARNING", "CRITICAL"):
            score += 20
            reasons.append(f"健康标签为 {health}")
        elif trend != "stable":
            score += 10
            reasons.append(f"趋势 {trend}")
        
        # 策略 4: 振动频谱特征
        if "spectral_sideband_ratio" in sensor_features:
            sbr = sensor_features.get("spectral_sideband_ratio", 0)
            if sbr > 0.15:
                score += 25
                reasons.append(f"边频带能量比 {sbr} 过高（轴承劣化信号）")
            elif sbr > 0.08:
                score += 12
                reasons.append(f"边频带能量比 {sbr} 偏高")
        
        # 策略 5: 谐波比
        hbr = sensor_features.get("spectral_harmonic_ratio", 0)
        if hbr > 0.3 and "spectral_harmonic_ratio" in sensor_features:
            score += 20
            reasons.append(f"谐波能量比 {hbr} 过高（齿轮磨损信号）")
        
        # 策略 6: 数据质量
        missing = sensor_features.get("missing_ratio", 0)
        if missing > 0.1:
            reasons.append(f"数据缺失 {missing*100:.0f}%，传感器可能故障")
            score += 15
        
        # 确定等级
        score = min(100, score)
        if score >= 80:
            level = "CRITICAL"
        elif score >= 60:
            level = "HIGH"
        elif score >= 40:
            level = "MEDIUM"
        elif score >= 20:
            level = "LOW"
        else:
            level = "NONE"
        
        return {
            "level": level,
            "score": score,
            "reasons": reasons,
        }
    
    def aggregate_equipment_anomaly(self, sensor_results: Dict[str, Dict]) -> Dict:
        """
        汇总一台设备所有传感器的异常评估。
        sensor_results: {sensor_code: detect_result}
        """
        if not sensor_results:
            return {"level": "NONE", "score": 0, "affected_sensors": []}
        
        total_score = 0
        max_level_score = {"CRITICAL": 80, "HIGH": 60, "MEDIUM": 40, "LOW": 20, "NONE": 0}
        affected = []
        
        for code, result in sensor_results.items():
            total_score += result["score"]
            if result["level"] != "NONE":
                affected.append({
                    "sensor": code,
                    "level": result["level"],
                    "score": result["score"],
                    "reasons": result["reasons"],
                })
        
        avg_score = total_score / len(sensor_results)
        max_level = max([max_level_score.get(r["level"], 0) for r in sensor_results.values()])
        
        final_score = max(avg_score, max_level)
        
        if final_score >= 70:
            level = "CRITICAL"
        elif final_score >= 50:
            level = "HIGH"
        elif final_score >= 30:
            level = "MEDIUM"
        elif final_score >= 15:
            level = "LOW"
        else:
            level = "NONE"
        
        return {
            "level": level,
            "score": round(final_score, 2),
            "affected_sensors": affected,
            "affected_count": len(affected),
            "total_sensors": len(sensor_results),
        }
