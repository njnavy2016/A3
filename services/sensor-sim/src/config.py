# Sensor Simulator 配置
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class SensorConfig:
    sensor_code: str
    sensor_type: str        # VIBRATION / TEMPERATURE / CURRENT / OIL_PRESSURE
    baseline: float
    normal_range: tuple     # (min, max)
    noise_level: float = 0.05
    degradation_rate: float = 0.0  # 每小时退化增量（模拟渐进式故障）


@dataclass
class EquipmentConfig:
    equipment_code: str
    sensors: List[SensorConfig] = field(default_factory=list)


# ============ 风力发电机齿轮箱默认配置 ============
DEFAULT_EQUIPMENTS = [
    EquipmentConfig(
        equipment_code="WT-GEAR-001",
        sensors=[
            SensorConfig("VIB_LS_X", "VIBRATION", 1.20, (0.30, 2.00), 0.08, 0.0),
            SensorConfig("VIB_LS_Y", "VIBRATION", 1.20, (0.30, 2.00), 0.08, 0.0),
            SensorConfig("VIB_LS_Z", "VIBRATION", 0.90, (0.20, 1.50), 0.06, 0.0),
            SensorConfig("VIB_HS_X", "VIBRATION", 1.00, (0.20, 1.80), 0.07, 0.0),
            SensorConfig("TEMP_BEARING_LS_FRONT", "TEMPERATURE", 50.0, (40.0, 60.0), 0.5, 0.0),
            SensorConfig("TEMP_OIL", "TEMPERATURE", 55.0, (45.0, 65.0), 0.6, 0.0),
            SensorConfig("OIL_PRESS", "OIL_PRESSURE", 3.20, (2.50, 4.00), 0.05, 0.0),
            SensorConfig("CURRENT_RMS", "CURRENT", 35.0, (25.0, 45.0), 1.5, 0.0),
        ]
    ),
    EquipmentConfig(
        equipment_code="WT-GEAR-003",   # 较旧设备，有退化趋势
        sensors=[
            SensorConfig("VIB_LS_X", "VIBRATION", 1.80, (0.30, 2.50), 0.12, 0.005),   # 每小时+0.005 mm/s
            SensorConfig("VIB_LS_Y", "VIBRATION", 1.75, (0.30, 2.50), 0.12, 0.005),
            SensorConfig("VIB_LS_Z", "VIBRATION", 1.30, (0.20, 2.00), 0.10, 0.003),
            SensorConfig("VIB_HS_X", "VIBRATION", 1.40, (0.20, 2.00), 0.10, 0.004),
            SensorConfig("TEMP_BEARING_LS_FRONT", "TEMPERATURE", 58.0, (40.0, 65.0), 0.8, 0.004),
            SensorConfig("TEMP_OIL", "TEMPERATURE", 62.0, (45.0, 68.0), 0.9, 0.003),
            SensorConfig("OIL_PRESS", "OIL_PRESSURE", 2.60, (2.30, 3.80), 0.08, -0.001),  # 缓慢下降
            SensorConfig("CURRENT_RMS", "CURRENT", 38.0, (25.0, 48.0), 2.0, 0.0),
        ]
    ),
]


# ============ 运行时模式 ============
SIM_MODE = os.environ.get("SIM_MODE", "degradation")  # normal / degradation / fault / test
SIM_SPEED = float(os.environ.get("SIM_SPEED", "1.0"))  # 1.0 = 实时，10.0 = 加速10倍

# 模式对应退化率覆盖
MODE_OVERRIDES = {
    "normal":      0.0,
    "degradation": 1.0,     # 使用默认 degradation_rate
    "fault":       5.0,     # 加速退化 + 注入故障
    "test":        0.0,     # 仅在 API 触发时注入
}


def get_mode_multiplier() -> float:
    return MODE_OVERRIDES.get(SIM_MODE, 1.0)
