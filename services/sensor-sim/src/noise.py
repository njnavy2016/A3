# 断连噪点生成器
import random
from typing import List, Optional


def inject_disconnection_events(
    series: List[float],
    probability: float = 0.005,   # 每个点出现断连的概率
    cluster_probability: float = 0.3,  # 断连成簇概率
    max_cluster_len: int = 12,    # 断连簇最大长度（点数）
    missing_repr: Optional[float] = None,  # 缺失值表示，None=删除
) -> List[Optional[float]]:
    """
    在时序数据中注入传感器断连事件。
    - 单点断连（模拟偶发信号丢失）
    - 成簇断连（模拟工业现场常见的通信中断）
    """
    result = []
    i = 0
    while i < len(series):
        if random.random() < probability:
            # 可能成簇断连
            if random.random() < cluster_probability:
                cluster_len = random.randint(2, max_cluster_len)
                for _ in range(min(cluster_len, len(series) - i)):
                    result.append(missing_repr)
                    i += 1
            else:
                result.append(missing_repr)
                i += 1
        else:
            result.append(series[i])
            i += 1
    return result


def inject_outliers(
    series: List[float],
    probability: float = 0.003,
    outlier_magnitude: float = 3.0,  # 相对标准差的倍数
) -> List[float]:
    """注入孤立异常点（工业传感器偶发脉冲干扰）"""
    if not series:
        return series
    
    values = [v for v in series if v is not None]
    if len(values) < 10:
        return series
    
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    std_val = variance ** 0.5
    
    result = []
    for v in series:
        if v is not None and random.random() < probability:
            direction = random.choice([-1, 1])
            v = round(mean_val + direction * outlier_magnitude * std_val, 4)
        result.append(v)
    return result
