"""API 入参 / 出参模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["windows", "macos", "linux"]


class IdentifyIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class SoftwareOut(BaseModel):
    id: int | None = None
    name: str
    display_name: str
    category: str | None = None
    source: str | None = None
    repo: str | None = None
    tag_pattern: str | None = None   # GitHub tag → 版本号 的正则
    exclude_pattern: str | None = None  # 排除的 tag（如 -rc / beta）
    min_major: int | None = None     # 过滤掉过老的大版本
    homepage: str | None = None
    platforms: list[str] = []
    aliases: list[str] = []


class IdentifyOut(BaseModel):
    software: SoftwareOut
    matched: bool            # 是否命中已知软件目录
    ai_used: bool


class VersionItem(BaseModel):
    version: str
    is_latest: bool = False


class VersionsOut(BaseModel):
    software: SoftwareOut
    versions: list[VersionItem]
    source: str              # cache / npm / pypi / github / maven / ai / seed
    cached: bool = False


class PlanIn(BaseModel):
    software: str
    version: str
    platform: Platform
    display_name: str | None = None
    homepage: str | None = None
    force: bool = False      # True 表示强制重新生成


class PlanOut(BaseModel):
    id: int
    software_name: str
    version: str
    platform: str
    markdown: str
    script: str | None = None
    script_type: str | None = None
    install_mode: str = "script"
    model: str | None = None
    valid_count: int = 0
    invalid_count: int = 0
    cached: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class FeedbackIn(BaseModel):
    plan_id: int | None = None
    software_name: str | None = None
    version: str | None = None
    platform: str | None = None
    rating: Literal["valid", "invalid"]
    content: str | None = Field(default=None, max_length=2000)


class StatIn(BaseModel):
    kind: Literal["software", "version", "platform", "install_run", "plan_generate"]
    key: str
    software_name: str | None = None
    platform: str | None = None


class LoginIn(BaseModel):
    password: str


class PlanUpdateIn(BaseModel):
    markdown: str


class PlanAdminIn(BaseModel):
    software: str
    version: str
    platform: Platform
