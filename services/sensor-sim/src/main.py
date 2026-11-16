# Sensor Simulator 主入口
import os
import sys
import asyncio
import random
import signal
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_EQUIPMENTS,
    SIM_MODE,
    SIM_SPEED,
    get_mode_multiplier,
)
from producer import DataProducer
from sequences.normal import generate_normal_value
from sequences.degradation import generate_degraded_value
from noise import inject_disconnection_events, inject_outliers


INTERVAL_SECONDS = 60 / SIM_SPEED  # 每"分钟"一个点（乘以速度倍率）


async def run_simulator():
    print(f"{'='*60}")
    print(f"  PdM Sensor Simulator")
    print(f"  模式: {SIM_MODE}  速度倍率: {SIM_SPEED}x")
    print(f"  间隔: {INTERVAL_SECONDS:.1f}s/点")
    print(f"{'='*60}")
    
    producer = DataProducer()
    await producer.connect()
    
    # 每个传感器的时间偏移（模拟设备启动时间不同）
    equipment_offsets = {}
    for eq in DEFAULT_EQUIPMENTS:
        equipment_offsets[eq.equipment_code] = random.uniform(0, 480)  # 0-8 小时
    
    # 故障注入状态（可被 API 触发修改）
    fault_injection = {"WT-GEAR-003": None}  # None / "bearing_pitting" / "oil_leak"
    
    iteration = 0
    try:
        while True:
            now = datetime.now(timezone.utc)
            time_step_hours = iteration * (INTERVAL_SECONDS / 3600.0)
            
            for eq in DEFAULT_EQUIPMENTS:
                offset = equipment_offsets[eq.equipment_code]
                effective_hours = max(0, time_step_hours - offset)
                
                # 检查故障注入
                fault = fault_injection.get(eq.equipment_code)
                
                for sensor in eq.sensors:
                    # 选择生成策略
                    degradation_mult = get_mode_multiplier()
                    
                    # 故障场景加速退化
                    if fault:
                        degradation_mult *= 10
                    
                    degradation_rate = sensor.degradation_rate * degradation_mult
                    
                    if degradation_rate > 0 or fault:
                        value = generate_degraded_value(
                            sensor.baseline, sensor.noise_level,
                            sensor.normal_range, effective_hours,
                            degradation_rate, sensor.sensor_type
                        )
                        
                        # 故障场景叠加额外特征
                        if fault == "bearing_pitting" and sensor.sensor_type == "VIBRATION":
                            # 注入更强的冲击和边频带调制
                            impact = random.gauss(0, degradation_rate * 20) if degradation_rate > 0 else 0
                            value += abs(impact)
                    else:
                        value = generate_normal_value(
                            sensor.baseline, sensor.noise_level,
                            sensor.normal_range, effective_hours,
                            sensor.sensor_type
                        )
                    
                    # 注入噪点（模拟真实传感器）
                    if random.random() < 0.003:
                        # 孤立异常点
                        std = sensor.noise_level * abs(sensor.baseline)
                        direction = random.choice([-1, 1])
                        value += direction * 3 * std
                    
                    # 推送
                    await producer.push_sensor_value(
                        eq.equipment_code, sensor.sensor_code, value, now
                    )
                    
                    # 输出日志
                    if iteration % 60 == 0:
                        print(f"[{now.strftime('%H:%M:%S')}] "
                              f"{eq.equipment_code}/{sensor.sensor_code}: {value:.4f}")
            
            iteration += 1
            await asyncio.sleep(INTERVAL_SECONDS)
    
    except asyncio.CancelledError:
        print("\n[Simulator] 收到停止信号，正在退出...")
    except KeyboardInterrupt:
        print("\n[Simulator] 手动停止")
    finally:
        await producer.disconnect()
        print("[Simulator] 已断开 Redis 连接")


async def graceful_shutdown(signum, frame):
    print(f"\n[Simulator] 收到信号 {signum}，准备关闭...")
    loop = asyncio.get_running_loop()
    for task in asyncio.all_tasks():
        task.cancel()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    try:
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        pass
