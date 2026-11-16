# 数据序列生成器：正常波动 + 日周期
import math
import random
from typing import List


def generate_normal_value(
    baseline: float,
    noise_level: float,
    normal_range: tuple,
    time_step_hours: float = 0.0,
    sensor_type: str = "",
) -> float:
    """
    生成单个正常工况数据点。
    - 随机高斯噪声
    - 温度类传感器叠加日周期（昼夜温差导致风机温度变化）
    - 振动类传感器叠加微弱周期性（风机转速脉动）
    """
    value = baseline
    
    # 1. 高斯噪声
    noise = random.gauss(0, noise_level * abs(baseline) if baseline != 0 else noise_level)
    value += noise
    
    # 2. 日周期（温度传感器）
    if sensor_type == "TEMPERATURE":
        # 24 小时周期，振幅 ~5℃
        day_cycle = 2.5 * math.sin(2 * math.pi * time_step_hours / 24.0)
        value += day_cycle
    
    # 3. 风机转速脉动（振动 + 电流）
    if sensor_type in ("VIBRATION", "CURRENT"):
        # 转速波动导致的低频调制
        rotor_freq = 0.3  # Hz（低速轴 20rpm ≈ 0.33Hz）
        mod = 0.05 * baseline * math.sin(2 * math.pi * rotor_freq * time_step_hours * 3600)
        value += mod
    
    # 4. 限制在正常范围内（80% 概率，有少量正常越界以模拟真实）
    if random.random() < 0.92:
        lo, hi = normal_range
        value = max(lo * 0.95, min(hi * 1.05, value))
    
    return round(value, 4)


def generate_series(
    count: int,
    baseline: float,
    noise_level: float,
    normal_range: tuple,
    interval_minutes: int = 1,
    sensor_type: str = "",
) -> List[float]:
    """生成一段连续时序数据"""
    series = []
    for i in range(count):
        time_hours = (i * interval_minutes) / 60.0
        val = generate_normal_value(baseline, noise_level, normal_range, time_hours, sensor_type)
        series.append(val)
    return series
