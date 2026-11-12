"""全局配置：从 .env 读取 AI 凭据、管理员密码等。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SERVER_DIR / ".env")


def _clean(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'")


class Settings:
    """轻量配置对象（避免引入 pydantic-settings，保持依赖精简）。"""

    def __init__(self) -> None:
        # 兼容两种命名：AI_API_KEY/AI_BASE_URL（推荐）与 ANTHROPIC_AUTH_TOKEN/ANTHROPIC_BASE_URL
        # （后者来自 ~/.claude/settings.json 的 env，由 scripts/sync_ai_config.py 写入）
        self.ai_api_key = _clean(os.getenv("AI_API_KEY")) or _clean(os.getenv("ANTHROPIC_AUTH_TOKEN"))
        # 兼容 Anthropic 风格地址：https://xxx/anthropic 需要补 /v1 再拼 /chat/completions
        self.ai_base_url = (_clean(os.getenv("AI_BASE_URL"))
                            or _clean(os.getenv("ANTHROPIC_BASE_URL"))
                            or "https://api.openai.com/v1")
        self.ai_model = _clean(os.getenv("AI_MODEL")) or "claude-sonnet-4-5"
        self.ai_timeout = float(_clean(os.getenv("AI_TIMEOUT")) or 180)
        # 单次输出上限。DeepSeek deepseek-chat 最大 8K，Claude/GPT 可设更大。
        self.ai_max_tokens = int(_clean(os.getenv("AI_MAX_TOKENS")) or 8000)
        # 允许显式关闭 AI（例如离线演示），关闭后一律走本地兜底方案
        self.ai_enabled = _clean(os.getenv("AI_ENABLED")).lower() not in {"0", "false", "no", "off"}

        self.admin_password = _clean(os.getenv("ADMIN_PASSWORD")) or "admin123"
        self.jwt_secret = _clean(os.getenv("JWT_SECRET")) or "zhuang-le-ma-dev-secret"
        self.db_path = Path(_clean(os.getenv("DB_PATH")) or (SERVER_DIR / "data" / "zhuang.db"))
        if not self.db_path.is_absolute():
            self.db_path = SERVER_DIR / self.db_path

        self.host = _clean(os.getenv("HOST")) or "127.0.0.1"
        self.port = int(_clean(os.getenv("PORT")) or 8017)
        # GitHub 匿名 API 限流严重，配置 token 可显著提升版本抓取成功率
        self.github_token = _clean(os.getenv("GITHUB_TOKEN"))

    @property
    def chat_completions_url(self) -> str:
        base = self.ai_base_url.rstrip("/")
        if not base.endswith("/v1") and not base.endswith("/v1beta"):
            base = f"{base}/v1"
        return f"{base}/chat/completions"

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_enabled and self.ai_api_key and self.ai_base_url)


settings = Settings()
