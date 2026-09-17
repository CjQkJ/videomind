"""VideoMind API 的 HTTP 客户端。

封装提交、轮询、结果下载等调用，供 CLI 与 skill scripts 复用。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Iterable, Optional

import requests

from .config import Config


class VideoMindError(Exception):
    """调用 VideoMind 服务时的网络或业务错误。"""


class Client:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.api_key}",
                "Accept": "application/json",
            }
        )

    # -- 内部工具 ----------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _request(
        self,
        method: str,
        path: str,
        action: str,
        *,
        timeout: int,
        **kwargs,
    ) -> requests.Response:
        try:
            return self.session.request(
                method,
                self._url(path),
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise VideoMindError(f"{action}失败：网络错误 - {exc}") from exc

    @staticmethod
    def _check(resp: requests.Response, action: str) -> dict:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text[:500]
            raise VideoMindError(f"{action}失败：HTTP {resp.status_code} - {detail}")
        try:
            return resp.json()
        except ValueError:
            return {}

    # -- 认证 / 服务 -------------------------------------------------------
    def me(self) -> dict:
        """当前用户信息（也用于验证 Key 是否有效）。"""
        resp = self._request("GET", "/api/v1/auth/me", "获取用户信息", timeout=20)
        return self._check(resp, "获取用户信息")

    def health(self) -> dict:
        """服务健康检查。"""
        resp = self._request("GET", "/api/v1/health", "健康检查", timeout=20)
        return self._check(resp, "健康检查")

    def upload(self, path: str | Path) -> dict:
        """Upload a local video and return its file_id metadata."""
        video_path = Path(path)
        if not video_path.is_file():
            raise VideoMindError(f"本地视频不存在：{video_path}")
        try:
            with video_path.open("rb") as handle:
                resp = self._request(
                    "POST",
                    "/api/v1/uploads",
                    "上传视频",
                    timeout=600,
                    files={"file": (video_path.name, handle, "application/octet-stream")},
                )
        except OSError as exc:
            raise VideoMindError(f"读取本地视频失败：{exc}") from exc
        return self._check(resp, "上传视频")

    # -- 任务 --------------------------------------------------------------
    def submit(
        self,
        *,
        url: Optional[str] = None,
        file_id: Optional[str] = None,
        mode: str = "study_note",
        formats: Optional[Iterable[str]] = None,
        show_source: bool = True,
        language: str = "zh-CN",
    ) -> dict:
        """提交一个理解任务，返回含 job_id / status / quota 的字典。"""
        if url and file_id:
            raise ValueError("url 与 file_id 不能同时提供")
        if url:
            input_obj: dict = {"type": "bilibili_url", "url": url}
        elif file_id:
            input_obj = {"type": "upload", "file_id": file_id}
        else:
            raise ValueError("必须提供 url 或 file_id")

        body = {
            "input": input_obj,
            "output": {
                "mode": mode,
                "formats": list(formats or ["json", "markdown"]),
            },
            "options": {"show_source": show_source, "language": language},
        }
        resp = self._request("POST", "/api/v1/jobs", "提交任务", timeout=30, json=body)
        return self._check(resp, "提交任务")

    def get(self, job_id: str) -> dict:
        """查询单个任务的状态与进度。"""
        resp = self._request("GET", f"/api/v1/jobs/{job_id}", "查询任务", timeout=20)
        return self._check(resp, "查询任务")

    def list_jobs(self, limit: int = 30) -> dict:
        """获取历史任务列表。"""
        resp = self._request(
            "GET", "/api/v1/jobs", "获取历史任务", timeout=20, params={"limit": limit}
        )
        return self._check(resp, "获取历史任务")

    def result(self, job_id: str) -> dict:
        """结果元数据 + 产物链接。"""
        resp = self._request(
            "GET", f"/api/v1/jobs/{job_id}/result", "获取结果元数据", timeout=20
        )
        return self._check(resp, "获取结果元数据")

    def result_bytes(self, job_id: str, fmt: str) -> bytes:
        """下载结果产物，fmt ∈ json / md / html。"""
        ext = {"json": "json", "md": "md", "markdown": "md", "html": "html"}.get(
            fmt, fmt
        )
        resp = self._request(
            "GET",
            f"/api/v1/jobs/{job_id}/result.{ext}",
            f"下载 {fmt}",
            timeout=60,
        )
        if resp.status_code >= 400:
            raise VideoMindError(f"下载 {fmt} 失败：HTTP {resp.status_code}")
        return resp.content

    def rerender(self, job_id: str, mode: str, show_source: bool = True) -> dict:
        """切换输出模式重新渲染（不重跑 AI）。"""
        body = {"mode": mode, "show_source": show_source}
        resp = self._request(
            "POST",
            f"/api/v1/jobs/{job_id}/rerender",
            "重渲",
            timeout=60,
            json=body,
        )
        return self._check(resp, "重渲")

    def wait(
        self,
        job_id: str,
        *,
        timeout: int = 1800,
        poll: int = 5,
        on_progress: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """轮询直到 succeeded / failed，仅在每个状态变化时回调一次。"""
        deadline = time.monotonic() + timeout
        last_sig = None
        while time.monotonic() < deadline:
            data = self.get(job_id)
            sig = (
                data.get("status"),
                data.get("stage"),
                data.get("progress"),
                data.get("segment_done"),
                data.get("segment_total"),
            )
            if sig != last_sig:
                if on_progress:
                    on_progress(data)
                last_sig = sig
            if data.get("status") in ("succeeded", "failed"):
                return data
            time.sleep(poll)
        raise VideoMindError(f"等待超时（{timeout}s）：任务仍未完成")
