# 🎬 VideoMind

> 把任意视频变成结构化知识：**学习笔记 · 文章 · 复习卡片 · 教学网页**。
> 一个项目，两块拼图：**服务端**（自己部署，做视频理解）+ **客户端**（CLI / Agent Skill，连上服务端用）。

```bash
pip install videomind
videomind "https://www.bilibili.com/video/BVxxxxxxxx"
```

VideoMind 会**真正看懂**视频（基于画面 + 声音，不是浅层字幕总结），萃取操作步骤、方法论、关键观点，产出可交付的 Markdown 笔记与结构化 JSON。长视频（最长 4 小时）自动分段处理。

---

## 🏗️ 项目结构

```
videomind/
├── src/videomind/        # 客户端：CLI（Typer）
├── skills/videomind/     # 客户端：Agent Skill（Claude Code / Codex 通用）
├── tests/                # 客户端测试
└── server/               # 服务端：FastAPI + Vue 3 + 部署模板
    ├── backend/          # 视频理解管线、认证、配额、Worker 队列
    ├── web/              # Vue 3 前端（工作台 + 管理后台）
    ├── deploy/           # systemd / Nginx / certbot 模板
    └── README.md         # 服务端部署说明
```

**只想用？** 装客户端，连一个已有服务端即可（见下方「配置」）。
**想自己跑一套？** 看 [`server/README.md`](server/README.md) 部署服务端。

---

## ✨ 特性

- 🎯 **深度理解**：画面细节 + 语音内容，不是字幕压缩
- 📝 **四种产物**：学习笔记 / 文章 / 复习卡片 / 教学网页
- ✂️ **长视频分段**：自动切段、重叠合并，最长 4 小时
- ⚡ **一条命令**：`videomind <链接>` 提交→等待→保存一步到位
- 🤖 **Agent Skill**：符合 [Agent Skills 开放标准](https://agentskills.io)，Claude Code / Codex 等通用
- 🖥️ **自带工作台**：服务端提供 Web 界面（提交、进度、结果阅读、历史、API Key 管理、管理后台）

---

## 📦 安装客户端

### 方式一：命令行工具

```bash
pip install videomind
```

### 方式二：作为 Agent Skill（Claude Code / Codex 等）

用 [skills CLI](https://github.com/vercel-labs/skills) 一键装进你的 AI agent：

```bash
# 装进 Claude Code（全局）
npx skills add CjQkJ/videomind --agent claude-code -g -y

# 装进 Codex 等（按 skills CLI 支持的 --agent 目标）
npx skills add CjQkJ/videomind --agent codex -g -y
```

> Skill 内部调用 `videomind` CLI，因此仍需 `pip install videomind`（现代 agent 会在首次使用时自动安装）。

---

## 🔑 配置

需要一个 `vw_` 开头的 API Key（在服务端工作台的「API Keys」页面创建），以及服务端地址：

```bash
# 连本机自部署的服务端（默认地址 http://127.0.0.1:8000）
videomind config set-key vw_你的API密钥

# 连远程服务端
videomind config set-key vw_你的API密钥 --base-url https://video.example.com
```

也可以用环境变量（适合 CI / 容器，优先级高于配置文件）：

```bash
export VIDEOMIND_API_KEY=vw_你的API密钥
export VIDEOMIND_BASE_URL=https://video.example.com
```

验证：

```bash
videomind whoami     # 显示当前账号与 tier
videomind health     # 服务状态与配额
```

---

## 🚀 快速开始

```bash
# 一条龙：提交 → 等待 → 保存到 ./job_<id>/result.md + result.json
videomind "https://www.bilibili.com/video/BVxxxxxxxx"

# 本地视频：自动 upload → submit → wait
videomind "./demo.mp4" --mode study_note

# 指定输出模式与保存位置
videomind "https://www.bilibili.com/video/BVxxxxxxxx" --mode cards -o ./notes/
```

处理时长：约每 10 分钟视频需要 2–3 分钟。长视频自动分段。

---

## 📋 命令参考

| 命令 | 说明 |
| :--- | :--- |
| `videomind <url-or-path>` | 一条龙；本地路径会先 multipart 上传 |
| `videomind run <url-or-path>` | 同上的显式写法；`submit` 仍只接受 URL |
| `videomind submit <url>` | 仅提交，立即返回 `job_id` |
| `videomind status <job_id>` | 查询任务进度 |
| `videomind wait <job_id>` | 轮询直到成功/失败 |
| `videomind result <job_id>` | 下载结果（`-f md\|json\|html`，`-o` 指定路径） |
| `videomind jobs` | 列出历史任务（`-n 限制条数`） |
| `videomind health` | 服务状态与配额 |
| `videomind whoami` | 验证 Key、显示账号 |
| `videomind config set-key <key>` | 保存 API Key |
| `videomind config show` | 查看配置（Key 脱敏） |

---

## 🎨 输出模式（`--mode`）

| 值 | 适用 | 产物 |
| :--- | :--- | :--- |
| `study_note` | 系统学习、做笔记（默认） | 结构化学习笔记 |
| `article` | 对外发布、博客 | 可读长文 |
| `cards` | 复习、速记 | 知识卡片 |
| `teaching_html` | 教学、演示 | HTML 网页；目录输出额外保存 `result.html` |

---

## 🤖 作为 Agent Skill 使用

装好 skill 后（见上方「方式二」），在你的 AI agent 里直接说：

> 「帮我总结这个视频：https://www.bilibili.com/video/BVxxxxxxxx」

agent 会自动调用 `videomind` CLI 提交视频、等待完成、读取笔记并给你摘要。

skill 自身是 agent-中立的：只用标准 frontmatter（`name` + `description`），不依赖任何单一 agent 的专有字段，因此兼容 Claude Code、Codex 及任何遵循 [Agent Skills 开放标准](https://agentskills.io) 的工具。

---

## 🖥️ 部署服务端

服务端包含视频理解管线、用户体系、配额队列、Web 工作台和管理后台，可独立部署：

```bash
cd server/backend
pip install -r requirements.txt
# 系统依赖：ffmpeg、ffprobe、yt-dlp

cat > .env <<'EOF'
OPENAI_BASE_URL=https://your-upstream-endpoint
OPENAI_API_KEY=your-upstream-key
SECRET_KEY=change-me-to-a-long-random-string
ADMIN_EMAIL=you@example.com
EOF

python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

完整说明（前端构建、systemd、Nginx、HTTPS、环境变量清单）见 [`server/README.md`](server/README.md)。

---

## 🛠️ 开发

```bash
git clone https://github.com/CjQkJ/videomind.git
cd videomind

# 客户端
pip install -e ".[test]"
pytest

# 服务端
cd server/backend && python -m pytest tests -q
cd ../web && npm install && npm test && npm run build
```

发布 wheel 会把 Skill 文件放到 `share/videomind/skills/videomind/`；pip 不会自动把它注册到某个 Agent，仍需按上面的 skills CLI 或手动安装。

---

## ❓ 常见问题

| 现象 | 处理 |
| :--- | :--- |
| `未配置 API Key` | 运行 `videomind config set-key <key>` 或设环境变量 |
| 连不上服务端 | 确认 `--base-url` 正确、服务端已启动、`videomind health` 可通 |
| 任务一直 `queued` | 并发已满，排队等待即可 |
| 任务 `failed` | 多为源视频下载失败（B 站风控）或时长超限，换链接重试 |
| 想换输出形式 | 重新 `videomind <url> --mode cards` |

---

## 📄 License

MIT © CjQkJ
