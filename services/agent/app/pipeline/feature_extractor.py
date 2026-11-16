# ================= 核心难题解决方案 =================
# 特征提取器：将高频时序数据压缩为紧凑特征摘要（≤2000 tokens）
# 设计原则：特征提取在 LLM 之外独立完成，LLM 只看结构化摘要
# =====================================================

import json
import numpy as np
from scipy import signal as scipy_signal
from datetime import datetime
from typing import List, Dict, Optional


class FeatureExtractor:
    """
    将原始时序数据转换为紧凑的特征字典。
    输入：raw_series (List[float]) —— 某传感器的原始时序
    输出：features (Dict) —— 可以直接序列化为 ≤500 tokens 的 JSON
    """
    
    def __init__(self, baseline: float, normal_range: tuple = None, sensor_type: str = "GENERIC"):
        self.baseline = baseline
        self.normal_range = normal_range or (0, float('inf'))
        self.sensor_type = sensor_type
    
    def extract(self, raw_series: List[float]) -> Dict:
        """提取全部特征"""
        series = np.array(raw_series, dtype=float)
        # 过滤 NaN
        series_clean = series[~np.isnan(series)]
        
        if len(series_clean) < 10:
            return self._empty_features(len(series))
        
        features = {}
        
        # ---- 1. 基础统计 ----
        features.update(self._basic_stats(series_clean))
        
        # ---- 2. 趋势 ----
        features.update(self._trend(series_clean))
        
        # ---- 3. 周期性 ----
        features.update(self._periodicity(series_clean))
        
        # ---- 4. 频谱特征（振动传感器专用）----
        if self.sensor_type in ("VIBRATION", "SPECTRUM"):
            features.update(self._spectral_features(series_clean))
        
        # ---- 5. 退化/偏离基线 ----
        features.update(self._degradation(series_clean))
        
        # ---- 6. 异常点检测 ----
        features.update(self._anomaly_detection(series_clean))
        
        # ---- 7. 缺失/噪点统计 ----
        features.update(self._missing_stats(series))
        
        # ---- 8. 健康状态标签 ----
        features["health_status"] = self._classify_health(features)
        
        return features
    
    def _basic_stats(self, s: np.ndarray) -> Dict:
        return {
            "mean": round(float(np.mean(s)), 4),
            "std": round(float(np.std(s)), 4),
            "min": round(float(np.min(s)), 4),
            "max": round(float(np.max(s)), 4),
            "range": round(float(np.max(s) - np.min(s)), 4),
            "rms": round(float(np.sqrt(np.mean(s**2))), 4),
        }
    
    def _trend(self, s: np.ndarray) -> Dict:
        """线性回归斜率（per sample）"""
        x = np.arange(len(s))
        n = len(s)
        slope = (n * np.sum(x * s) - np.sum(x) * np.sum(s)) / (n * np.sum(x**2) - np.sum(x)**2) if n > 1 else 0
        # 计算首尾差
        diff_first_last = float(s[-1] - s[0])
        return {
            "slope_per_sample": round(float(slope), 6),
            "trend_direction": "up" if slope > 0 else ("down" if slope < 0 else "stable"),
            "first_val": round(float(s[0]), 4),
            "last_val": round(float(s[-1]), 4),
            "change_rate": round(diff_first_last / max(abs(s[0]), 1e-9) * 100, 2),  # %
        }
    
    def _periodicity(self, s: np.ndarray) -> Dict:
        """简单自相关检测周期性"""
        if len(s) < 50:
            return {"has_periodicity": False}
        
        try:
            autocorr = np.correlate(s - np.mean(s), s - np.mean(s), mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            # 找第二个峰值（第一个是 lag=0）
            peaks, _ = scipy_signal.find_peaks(autocorr[1:], height=np.max(autocorr[1:]) * 0.3)
            if len(peaks) > 0:
                period_lag = int(peaks[0]) + 1
                return {"has_periodicity": True, "dominant_period_lag": period_lag}
        except Exception:
            pass
        return {"has_periodicity": False}
    
    def _spectral_features(self, s: np.ndarray) -> Dict:
        """FFT 频谱特征（振动分析核心）"""
        if len(s) < 32:
            return {}
        
        try:
            # 去除均值
            s_centered = s - np.mean(s)
            # Hann 窗
            window = np.hanning(len(s_centered))
            windowed = s_centered * window
            
            fft_vals = np.abs(np.fft.rfft(windowed))
            fft_freqs = np.fft.rfftfreq(len(s_centered))
            
            total_energy = np.sum(fft_vals**2)
            if total_energy == 0:
                return {}
            
            # 找主导频率
            dominant_idx = np.argmax(fft_vals[1:]) + 1
            dominant_freq_norm = float(fft_freqs[dominant_idx])
            
            # 谐波能量比（2x, 3x）
            harmonic_ratio = 0
            for mult in (2, 3):
                target = dominant_idx * mult
                if target < len(fft_vals):
                    harmonic_ratio += float(fft_vals[target]**2) / total_energy
            
            # 边频带能量（±20% 邻域）
            sideband_ratio = 0
            if dominant_idx > 5:
                lo = max(1, int(dominant_idx * 0.8) - dominant_idx)
                hi = min(len(fft_vals) - 1, dominant_idx + dominant_idx)
                sideband_energy = np.sum(fft_vals[lo:hi+1]**2) - float(fft_vals[dominant_idx]**2)
                sideband_ratio = float(sideband_energy / total_energy)
            
            return {
                "spectral_dominant_freq_norm": round(dominant_freq_norm, 4),
                "spectral_harmonic_ratio": round(harmonic_ratio, 4),
                "spectral_sideband_ratio": round(sideband_ratio, 4),
                "spectral_energy_concentration": round(
                    float(fft_vals[dominant_idx]**2 / total_energy), 4
                ),
            }
        except Exception as e:
            return {"spectral_error": str(e)[:50]}
    
    def _degradation(self, s: np.ndarray) -> Dict:
        """计算偏离健康基线的程度"""
        if self.baseline is None or self.baseline == 0:
            return {"degradation_index": 0}
        
        current_mean = float(np.mean(s))
        deviation_pct = (current_mean - self.baseline) / abs(self.baseline) * 100
        
        # 计算退化指数（0=健康，100=完全退化）
        # 用 normal_range 的宽度做归一化
        lo, hi = self.normal_range
        width = (hi - lo) if hi != float('inf') and lo != 0 else max(abs(self.baseline) * 2, 1)
        
        deviation_from_baseline = abs(current_mean - self.baseline)
        degradation_index = min(100.0, deviation_from_baseline / width * 100)
        
        return {
            "baseline": round(float(self.baseline), 4),
            "current_mean": round(current_mean, 4),
            "deviation_pct": round(deviation_pct, 2),
            "degradation_index": round(degradation_index, 2),
        }
    
    def _anomaly_detection(self, s: np.ndarray) -> Dict:
        """简单统计异常检测"""
        mean = np.mean(s)
        std = np.std(s)
        
        if std == 0:
            return {"outlier_ratio": 0.0}
        
        # 3-sigma 之外的点数
        outliers = np.sum(np.abs(s - mean) > 3 * std)
        outlier_ratio = float(outliers / len(s))
        
        # 与阈值对比
        lo, hi = self.normal_range
        threshold_violations = 0
        if lo != 0 or hi != float('inf'):
            threshold_violations = int(np.sum((s < lo) | (s > hi)))
        
        return {
            "outlier_ratio": round(outlier_ratio, 4),
            "threshold_violations": threshold_violations,
            "threshold_violation_ratio": round(threshold_violations / len(s), 4),
        }
    
    def _missing_stats(self, s: np.ndarray) -> Dict:
        total = len(s)
        nans = int(np.sum(np.isnan(s)))
        return {
            "total_points": total,
            "missing_points": nans,
            "missing_ratio": round(nans / max(total, 1), 4),
        }
    
    def _classify_health(self, features: Dict) -> str:
        """综合评估健康状态"""
        degradation = features.get("degradation_index", 0)
        threshold_violations = features.get("threshold_violations", 0)
        trend = features.get("trend_direction", "stable")
        
        if degradation > 70 or threshold_violations > 10:
            return "CRITICAL"
        elif degradation > 40 or threshold_violations > 3:
            return "WARNING"
        elif degradation > 20 or trend != "stable":
            return "MONITOR"
        else:
            return "HEALTHY"
    
    def _empty_features(self, total_points: int) -> Dict:
        return {
            "total_points": total_points,
            "data_quality": "insufficient",
            "health_status": "UNKNOWN",
        }


def format_features_for_llm(sensor_code: str, features: Dict) -> str:
    """将特征字典格式化为 LLM 友好的紧凑文本（减少 token）"""
    lines = [f"### 传感器 {sensor_code}"]
    
    if features.get("data_quality") == "insufficient":
        lines.append("- 数据点不足，跳过分析")
        return "\n".join(lines)
    
    # 基础
    lines.append(f"- 均值={features['mean']}  范围=[{features['min']}, {features['max']}]  RMS={features.get('rms','-')}")
    
    # 退化
    if "degradation_index" in features:
        lines.append(f"- 退化指数={features['degradation_index']}%  基线偏离={features['deviation_pct']}%")
    
    # 趋势
    if "trend_direction" in features:
        lines.append(f"- 趋势: {features['trend_direction']}  变化率={features['change_rate']}%  斜率={features['slope_per_sample']}")
    
    # 频谱（振动）
    if "spectral_harmonic_ratio" in features:
        lines.append(f"- 谐波能量比={features['spectral_harmonic_ratio']}  边频带能量={features['spectral_sideband_ratio']}")
    
    # 异常
    if "outlier_ratio" in features:
        lines.append(f"- 异常点比={features['outlier_ratio']*100:.1f}%  阈值违规={features['threshold_violations']}")
    
    # 健康标签
    lines.append(f"- 健康标签: {features['health_status']}")
    
    return "\n".join(lines)
