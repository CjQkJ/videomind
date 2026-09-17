---
name: videomind
description: Understand and take structured notes on videos. Use when the user shares a Bilibili video link (bilibili.com or b23.tv) or wants to summarize / extract knowledge from a video. Produces study notes, articles, flashcards, or teaching HTML from the video's actual visual + audio content (not just subtitles). Requires the `videomind` CLI (`pip install videomind`) and a VideoMind API key.
license: MIT
---

# VideoMind — 视频理解 Skill

把任意 B 站视频（或上传的视频文件）变成**结构化知识**：学习笔记、文章、复习卡片、教学网页。理解基于画面 + 声音，不是浅层字幕总结。

## 何时使用

- 用户给出 `bilibili.com` / `b23.tv` 链接，想总结、做笔记、提炼要点
- 用户问「这个视频讲了什么」「帮我看下这个视频」
- 用户想把教程/讲座视频变成可复习的卡片或笔记

## 前置依赖

首次使用前，确保已安装 CLI 并配置 API Key（用户会提供 key）：

```bash
pip install videomind
videomind config set-key vw_用户的API密钥
```

> 若 `videomind` 未安装，先执行 `pip install videomind`；配置只需一次。

## 如何使用（通过 Bash 工具调用 CLI）

### 一条龙：提交 → 等待 → 保存（推荐）

```bash
videomind "https://www.bilibili.com/video/BVxxxxxxxx" --mode study_note
```

完成后会在当前目录生成 `job_<id>/result.md` 与 `result.json`。长视频（>15 分钟）会自动分段，耗时更长（约每 10 分钟视频需 2–3 分钟处理）。

本地视频同样支持一条龙，CLI 会先上传再提交：

```bash
videomind "/path/to/demo.mp4" --mode study_note
```

当模式为 `teaching_html` 且输出为目录时，还会保存 `result.html`。辅助脚本 `scripts/videomind_skill.py` 仍只接受 B 站 URL，并把 Markdown 写到 stdout。

### 备选：直接输出 Markdown 到 stdout

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/videomind_skill.py "https://www.bilibili.com/video/BVxxxxxxxx" --mode cards
```

进度信息走 stderr，Markdown 笔记走 stdout，便于直接读取。

### 分步操作（大视频不想阻塞时）

```bash
videomind submit "<url>"          # 立即返回 job_id
videomind status <job_id>         # 查进度
videomind result <job_id> -f md   # 下载结果
```

## 输出模式（`--mode`）

| 值 | 适用 |
| :--- | :--- |
| `study_note` | 系统学习、做笔记（默认） |
| `article` | 对外发布、博客长文 |
| `cards` | 复习、速记卡片 |
| `teaching_html` | 教学/演示，产出 HTML |

## 推荐工作流

1. 拿到链接 → 执行 `videomind "<url>"`，等待完成
2. 读取生成的 `result.md`，向用户呈现：主旨摘要 + 关键章节 + 核心观点
3. 用户若想换形式（如「做成卡片」），用 `--mode cards` 重新提交，或参考 `references/api.md` 用 rerender

## 注意

- 处理异步进行，一条龙命令会阻塞直到完成（默认超时 30 分钟）
- 配额：普通用户并发 2、全站硬上限 4；满载时任务排队
- 单条任务消耗一次视频理解额度，对长视频请确认用户确实需要

## 参考

完整接口与字段说明见 [`references/api.md`](./references/api.md)。
