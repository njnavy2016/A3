# Redis 客户端封装
import os
import redis.asyncio as aioredis
from ..config import settings


class RedisClient:
    def __init__(self):
        self.redis: aioredis.Redis = None
    
    async def connect(self):
        self.redis = await aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        await self.redis.ping()
        print("[Backend.RedisClient] 连接成功")
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            self.redis = None


redis_client = RedisClient()
