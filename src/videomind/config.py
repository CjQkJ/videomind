"""配置管理：API Key 与服务地址。

读取顺序：环境变量 > 本地配置文件（``~/.config/videomind/config.json``）。
``videomind config set-key`` 写入本地文件；CI 等场景推荐用环境变量。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# 默认指向本机自部署的服务端（见仓库 server/ 目录）
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
ENV_KEY = "VIDEOMIND_API_KEY"
ENV_BASE = "VIDEOMIND_BASE_URL"

NOT_CONFIGURED_HINT = (
    "未配置 API Key。请运行 `videomind config set-key <vw_开头的key>`，"
    "或设置环境变量 VIDEOMIND_API_KEY。\n"
    "若服务端不在本机，请同时指定地址："
    "`videomind config set-key <key> --base-url https://你的域名`"
)


def config_path() -> Path:
    """返回本地配置文件路径。"""
    return Path.home() / ".config" / "videomind" / "config.json"


@dataclass
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL


def _resolve_base_url(base_url: str | None) -> str:
    """空值回退到默认地址，其余按用户输入原样保留。"""
    value = (base_url or "").strip()
    return value or DEFAULT_BASE_URL


def load() -> Config:
    """加载配置：环境变量优先，回退本地文件。未配置则抛 SystemExit。"""
    key = os.environ.get(ENV_KEY)
    base = os.environ.get(ENV_BASE)

    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        key = key or data.get("api_key")
        base = base or data.get("base_url")

    if not key:
        raise SystemExit(NOT_CONFIGURED_HINT)
    return Config(api_key=key, base_url=_resolve_base_url(base))


def save(api_key: str, base_url: str | None = None) -> Config:
    """把 API Key 写入本地配置文件（权限收紧到 0600）。"""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = _resolve_base_url(base_url)
    data = {"api_key": api_key, "base_url": resolved}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows 上 chmod 语义有限，忽略即可
        pass
    return Config(api_key=api_key, base_url=resolved)
