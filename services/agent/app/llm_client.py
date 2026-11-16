# LLM 客户端 —— 封装 OpenAI 兼容 API 调用
import os
import json
import httpx
from typing import List, Dict, Optional
from ..config import config


class LLMClient:
    """
    统一的 LLM 调用客户端。
    支持 OpenAI / DeepSeek / 任何 OpenAI 兼容 API。
    """
    
    def __init__(self):
        self.api_key = config.LLM_API_KEY
        self.base_url = config.LLM_BASE_URL.rstrip("/")
        self.model = config.LLM_MODEL
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
    
    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 4000,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        发送聊天请求。
        返回 LLM 的文本回复。
        """
        if not self.api_key:
            # 模拟模式：没有 API Key 时返回占位符
            return self._mock_response(messages)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return content.strip() if content else ""
            return ""
            
        except httpx.HTTPStatusError as e:
            print(f"[LLM] HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
            return self._error_fallback(f"HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            print(f"[LLM] 连接错误: {e}")
            return self._error_fallback("LLM 服务连接失败")
        except Exception as e:
            print(f"[LLM] 未知错误: {e}")
            return self._error_fallback(str(e))
    
    async def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ):
        """流式输出（SSE）"""
        if not self.api_key:
            yield self._mock_response(messages)
            return
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
    
    def _mock_response(self, messages: List[Dict]) -> str:
        """模拟 LLM 响应（无 API Key 时使用）"""
        # 从最后一个用户消息提取上下文
        user_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
        content_preview = (user_msg["content"][:200] if user_msg else "无上下文")
        
        return f"""## (模拟 LLM 响应 - 未配置 API Key)

### 根因分析（示例输出）

基于特征数据的规则引擎分析：

**最可能根因：轴承外圈早期点蚀** (置信度 78%)
- 证据：VIBRATION 边频带能量比 0.18 > 阈值 0.15
- 证据：轴承温度上升趋势 +2℃/周
- 匹配手册章节 3.2

### RUL 预估
- 预估剩余寿命：**120 ± 36 小时**
- 置信度：0.65

### 建议动作
1. 将润滑油更换周期缩短 50%
2. 增加振动监测频率至每 4 小时一次
3. 计划在下一个维护窗口（7 天内）更换轴承

### 工单建议（将触发人工审批）
```json
{{"order_type": "CORRECTIVE", "priority": "HIGH", "title": "WT-GEAR-003 轴承更换"}}
```

---
⚠️ **这是模拟输出**。请在 .env 中配置 `LLM_API_KEY` 以启用真实 LLM 推理。

上下文预览：{content_preview}...
"""
    
    def _error_fallback(self, reason: str) -> str:
        return f"""## ⚠️ LLM 调用失败

原因：{reason}

### 降级响应（规则引擎分析结果）

规则引擎已完成基础分析，请查看系统中的规则匹配结果。
如需完整 LLM 分析，请检查 LLM API 配置。
"""
    
    async def close(self):
        await self.client.aclose()


# 全局单例
llm_client = LLMClient()
