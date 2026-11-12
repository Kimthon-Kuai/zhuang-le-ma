"""识别准确性回归：本地目录命中率（不需要 AI 就该命中）。"""
import asyncio

import httpx

CASES = [
    "我想装 MySQL", "帮我搞 Node", "帮我搞个 Node.js", "want python", "装个 Redis 玩玩",
    "Java 开发环境怎么装", "jdk17", "我想学 Git", "Go 语言环境", "要不要装 Docker",
    "MySQL8", "nodejs 环境", "maven 怎么配", "Nginx", "VS Code", "IDEA 社区版",
    "postgresql 数据库", "mongodb", "rustup", "nvm", "pnpm", "Homebrew",
    "一个完全不存在的东西 XYZ",
]


async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8017", timeout=120) as c:
        ok = 0
        for text in CASES:
            j = (await c.post("/api/identify", json={"text": text})).json()
            flag = "LOCAL" if j["matched"] else ("AI   " if j["ai_used"] else "FALLB")
            if j["matched"]:
                ok += 1
            print(f"{flag} {text:26} -> {j['software']['display_name']}")
        print(f"\n本地命中 {ok}/{len(CASES)}")


asyncio.run(main())
