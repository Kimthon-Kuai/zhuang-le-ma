"""AI 调用层：OpenAI 兼容的 /v1/chat/completions。

所有 AI 能力（识别软件名、兜底版本列表、生成安装方案）都走这里，
方便统一处理超时、重试、错误信息。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from .config import settings


class AIError(RuntimeError):
    """AI 调用失败（未配置 / 网络 / 返回格式异常）。"""


@dataclass
class AIResult:
    content: str
    model: str
    finish_reason: str | None = None


def ai_configured() -> bool:
    return settings.ai_configured


async def chat(messages: list[dict], *, temperature: float = 0.3,
               max_tokens: int | None = None, json_mode: bool = False) -> AIResult:
    if not settings.ai_configured:
        raise AIError("AI 未配置：请在 server/.env 中设置 AI_API_KEY（或 ANTHROPIC_AUTH_TOKEN）与 AI_BASE_URL")

    # 不允许超过配置上限：DeepSeek deepseek-chat 最大 8K，超了会被网关拒绝
    max_tokens = min(max_tokens or settings.ai_max_tokens, settings.ai_max_tokens)

    payload: dict = {
        "model": settings.ai_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
        # 部分网关（Cloudflare）会根据 UA 拦截默认的 python-httpx
        "User-Agent": "zhuang-le-ma/1.0",
    }

    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.ai_timeout, connect=20)) as client:
        for attempt in range(2):
            try:
                resp = await client.post(settings.chat_completions_url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    body = resp.text[:600]
                    # 网关不支持 json_object 时降级重试
                    if resp.status_code == 400 and "response_format" in payload:
                        payload.pop("response_format", None)
                        continue
                    raise AIError(f"AI 接口返回 {resp.status_code}: {body}")
                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                content = choice.get("message", {}).get("content") or ""
                if not content.strip():
                    raise AIError("AI 返回了空内容")
                return AIResult(content=content,
                                model=data.get("model") or settings.ai_model,
                                finish_reason=choice.get("finish_reason"))
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = exc
                if attempt == 0:
                    continue
                raise AIError(f"AI 网络错误：{exc}") from exc
            except json.JSONDecodeError as exc:
                raise AIError(f"AI 返回内容不是合法 JSON：{exc}") from exc
    raise AIError(f"AI 调用失败：{last_err}")


def extract_json(text: str) -> dict:
    """从模型输出里抠出 JSON（兼容 ```json 包裹、前后废话）。"""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise
