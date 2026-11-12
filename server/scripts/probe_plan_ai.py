"""直接验证 AI 生成方案这一步（绕过缓存，看 AI 到底成功还是失败）。

用法：python scripts/probe_plan_ai.py [软件名]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ai, prompts, services  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "mysql"
    print(f"ai_configured = {settings.ai_configured}, model = {settings.ai_model}")

    sw, _, _ = await services.identify(name)
    print(f"识别: {sw.display_name} (source={sw.source}, repo={sw.repo})")

    mode = services.detect_install_mode(sw)
    print(f"install_mode = {mode}")

    prompt = prompts.plan_user_prompt(
        display_name=sw.display_name, version="8.4.0", platform="windows",
        homepage=sw.homepage, install_mode=mode,
        source_hint=f"source={sw.source}, repo={sw.repo}" if sw.repo else None,
    )
    print(f"prompt 长度 = {len(prompt)}")

    try:
        result = await ai.chat(
            [{"role": "system", "content": prompts.PLAN_SYSTEM},
             {"role": "user", "content": prompt}],
            temperature=0.25, max_tokens=7000,
        )
    except ai.AIError as exc:
        print(f"\n[AI 调用失败] {exc}")
        return 1

    print(f"\n[AI 调用成功] model={result.model} finish={result.finish_reason}")
    print(f"返回长度 = {len(result.content)}")
    print("\n--- 前 30 行 ---")
    print("\n".join(result.content.splitlines()[:30]))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
