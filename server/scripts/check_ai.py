"""快速验证 AI 是否真的能调通（不落库、不生成方案，只发一次最小请求）。

用法：python scripts/check_ai.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ai  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> int:
    print("== 配置 ==")
    print(f"  接口: {settings.chat_completions_url}")
    print(f"  模型: {settings.ai_model}")
    print(f"  上限: {settings.ai_max_tokens}")
    if not settings.ai_configured:
        print("\n[失败] AI 未配置：.env 里 Key 为空")
        return 1

    print("\n== 发送最小请求（问模型自己是谁）==")
    try:
        result = await ai.chat(
            [{"role": "user", "content": "只回答四个字：连接成功"}],
            temperature=0.0, max_tokens=64,
        )
    except ai.AIError as exc:
        msg = str(exc)
        print(f"\n[失败] {msg}")
        if "401" in msg:
            print("  → Key 无效或已失效：去 platform.deepseek.com 重新创建一个")
        elif "402" in msg or "Insufficient" in msg or "余额" in msg:
            print("  → 账户余额不足：去 platform.deepseek.com 充值（几块钱即可）")
        elif "404" in msg:
            print("  → 接口地址不对：ANTHROPIC_BASE_URL 应为 https://api.deepseek.com")
        elif "429" in msg:
            print("  → 请求太频繁，稍等几秒重试")
        else:
            print("  → 检查网络能否访问 api.deepseek.com（可能需要代理）")
        return 2

    print(f"  ✔ 模型回复: {result.content.strip()[:80]}")
    print(f"  ✔ 实际模型: {result.model}")
    print(f"  ✔ finish  : {result.finish_reason}")
    print("\n[成功] DeepSeek 已接通 🎉")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
