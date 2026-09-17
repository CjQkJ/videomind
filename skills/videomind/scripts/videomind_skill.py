#!/usr/bin/env python3
"""VideoMind skill 脚本：提交视频并输出 Markdown 笔记到 stdout。

用法：
    python3 videomind_skill.py <B站链接> [--mode study_note|article|cards|teaching_html]

供 Claude Code / Codex 等 agent 通过 Bash 工具调用。
- 进度信息输出到 stderr
- Markdown 笔记输出到 stdout（便于 agent 直接读取）
依赖：``pip install videomind``
"""
from __future__ import annotations

import argparse
import sys

try:
    from videomind.client import Client, VideoMindError
    from videomind.config import load
except ImportError:
    sys.stderr.write(
        "错误：未安装 videomind。请先运行 `pip install videomind`。\n"
    )
    sys.exit(1)


def _err(msg: str) -> None:
    sys.stderr.write(f"[videomind] {msg}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VideoMind skill：提交视频并输出 Markdown 笔记"
    )
    parser.add_argument("url", help="B 站视频链接")
    parser.add_argument(
        "--mode",
        default="study_note",
        choices=["study_note", "article", "cards", "teaching_html"],
    )
    parser.add_argument("--poll", type=int, default=5, help="轮询间隔秒数")
    args = parser.parse_args()

    try:
        cfg = load()
    except SystemExit as exc:
        _err(str(exc))
        return 1

    client = Client(cfg)
    try:
        created = client.submit(url=args.url, mode=args.mode)
    except VideoMindError as exc:
        _err(str(exc))
        return 1

    job_id = created["job_id"]
    _err(f"已提交 {job_id}")

    def on_progress(data: dict) -> None:
        _err(f"{data.get('progress', 0)}%  {data.get('message', '')}")

    try:
        final = client.wait(job_id, poll=args.poll, on_progress=on_progress)
    except VideoMindError as exc:
        _err(str(exc))
        return 1

    if final.get("status") != "succeeded":
        _err(f"任务失败：{final.get('message', '未知原因')}")
        return 2

    try:
        markdown = client.result_bytes(job_id, "md").decode("utf-8", "replace")
    except VideoMindError as exc:
        _err(str(exc))
        return 1

    sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
