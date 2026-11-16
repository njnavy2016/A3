# Redis 数据推送
import os
import json
import time
import redis.asyncio as aioredis
from datetime import datetime, timezone


REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


class DataProducer:
    """将传感器数据推送到 Redis，供 Agent 和 Backend 消费"""
    
    def __init__(self):
        self.redis: aioredis.Redis = None
    
    async def connect(self):
        self.redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        # 确保 MinIO bucket 存在（用 Redis key 作为 bucket 存在性标记）
        await self.redis.ping()
        print("[DataProducer] Redis 连接成功")
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
    
    async def push_sensor_value(
        self,
        equipment_code: str,
        sensor_code: str,
        value: float,
        timestamp: datetime = None,
    ):
        """
        推送单个传感器读数到 Redis。
        
        Key 设计：
        - 实时层：   realtime:{equipment}:{sensor} → Hash (最近 3600 条点)
        - 最新值：   latest:{equipment}:{sensor}   → String
        - 时间序列： ts:{equipment}:{sensor}       → ZSet (timestamp → value)
        """
        if self.redis is None:
            raise RuntimeError("Redis 未连接")
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_epoch = timestamp.timestamp()
        
        # 1. 更新最新值
        await self.redis.set(
            f"latest:{equipment_code}:{sensor_code}",
            json.dumps({"value": value, "ts": ts_str}),
            ex=86400  # 24h 过期
        )
        
        # 2. 追加到时间序列 ZSet（限制 86400 条 = 约 60 天@1分钟）
        key = f"ts:{equipment_code}:{sensor_code}"
        await self.redis.zadd(key, {json.dumps({"v": value, "t": ts_str}): ts_epoch})
        # 裁剪
        await self.redis.zremrangebyrank(key, 0, -86400)
        
        # 3. 发布到实时频道（供 WebSocket 订阅）
        await self.redis.publish(
            f"channel:{equipment_code}",
            json.dumps({"sensor": sensor_code, "value": value, "ts": ts_str})
        )
    
    async def push_batch(
        self,
        equipment_code: str,
        sensor_values: dict,   # {sensor_code: [(value, timestamp), ...]}
    ):
        """批量推送"""
        for sensor_code, readings in sensor_values.items():
            for value, ts in readings:
                await self.push_sensor_value(equipment_code, sensor_code, value, ts)
