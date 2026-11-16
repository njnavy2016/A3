# 退化与故障特征生成器
import math
import random
from typing import List


def generate_degraded_value(
    baseline: float,
    noise_level: float,
    normal_range: tuple,
    time_step_hours: float,
    degradation_rate: float,
    sensor_type: str = "",
) -> float:
    """
    生成渐进式退化的数据点。
    - 在正常波动基础上叠加随时间增长的退化分量
    - 偶尔出现异常冲击（模拟轴承点蚀产生的冲击脉冲）
    """
    # 先算正常基线值
    value = baseline
    
    # 退化趋势（线性增长）
    degradation = degradation_rate * time_step_hours
    
    # 非线性加速退化（早期缓慢 → 后期加速，符合浴盆曲线）
    if time_step_hours > 500:  # 20 天后加速
        degradation *= 1.5
    
    value += degradation
    
    # 高斯噪声
    noise = random.gauss(0, noise_level * abs(baseline) if baseline != 0 else noise_level)
    value += noise
    
    # 日周期（温度）
    if sensor_type == "TEMPERATURE":
        day_cycle = 2.5 * math.sin(2 * math.pi * time_step_hours / 24.0)
        value += day_cycle
    
    # 冲击脉冲（轴承点蚀特征）
    if sensor_type == "VIBRATION" and random.random() < 0.02:  # 2% 概率
        impact_amp = degradation * random.uniform(0.5, 2.0)
        value += impact_amp
    
    # 边频带调制（模拟调制信号）
    if sensor_type == "VIBRATION" and degradation > 0.5:
        mod_freq = 0.3  # 低速轴转频 ~20rpm
        sideband = 0.1 * degradation * math.sin(2 * math.pi * mod_freq * time_step_hours * 3600)
        value += sideband
    
    # 限制
    lo, hi = normal_range
    value = max(lo * 0.8, min(hi * 1.3, value))
    
    return round(value, 4)


def generate_degraded_series(
    count: int,
    baseline: float,
    noise_level: float,
    normal_range: tuple,
    degradation_rate: float,
    interval_minutes: int = 1,
    sensor_type: str = "",
) -> List[float]:
    series = []
    for i in range(count):
        time_hours = (i * interval_minutes) / 60.0
        val = generate_degraded_value(
            baseline, noise_level, normal_range, time_hours, degradation_rate, sensor_type
        )
        series.append(val)
    return series
