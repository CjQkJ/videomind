# VideoMind Server

VideoMind 的服务端：FastAPI 后端 + Vue 3 前端 + 部署模板。配合仓库根目录的 CLI / Agent Skill 使用。

## 目录

```text
backend/
  main.py, pipeline.py    # API 装配与视频理解管线
  app/                    # 配置、DB、鉴权、配额、Worker、任务执行
  scripts/                # set_vip、sanitize_job_secrets
  tests/                  # 后端安全/队列/教学 HTML 回归
  jobs_data/              # SQLite 与任务产物（运行时写入）
  uploads_data/           # 上传原始视频（运行时写入）
web/
  src/                    # Vue 3 + Naive UI
  tests/                  # Vitest 安全/响应式/状态回归
  dist/                   # npm run build 生成，Nginx 生产根目录
frontend/index.html       # 旧 Vanilla UI，仅保留作迁移参考
deploy/                   # systemd / Nginx / certbot 模板
```

## 能力

- B 站 URL 或本地视频上传；默认 native 原生音画理解（画面 + 语音，非字幕压缩）。
- `study_note`、`article`、`cards`、`teaching_html` 四种输出。
- 4 小时上限、长视频分段、DB Worker 队列和 Guest/User/VIP 配额。
- 已认证任务私有；访客任务是随机 `job_id` 只读链接，访客不能重渲。
- Markdown 使用 DOMPurify；教学 HTML 使用 sandbox iframe；后端 HTML 带 CSP。
- 客户端不能传上游 URL、Key、模型、时长或理解模式；这些只由服务端环境变量控制。
- 管理后台（`ADMIN_EMAIL` 指定的账号可见）：用户 / 使用记录 / API Key / 模型热改。

## 快速启动（本地）

> ⚠️ **模型要求**：必须使用支持**原生视频理解**的模型（视频画面 + 音频直接输入），推荐 **Gemini**。
> 默认 `gemini-3.6-flash-high` 走 Antigravity 原生视频路由；纯文本模型或不支持视频输入的模型无法工作。

```bash
cd server/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 系统依赖：ffmpeg、ffprobe、yt-dlp

cat > .env <<'EOF'
OPENAI_BASE_URL=https://your-upstream-endpoint
OPENAI_API_KEY=your-upstream-key
DEFAULT_MODEL=gemini-3.6-flash-high
SECRET_KEY=change-me-to-a-long-random-string
EOF

python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd server/web
npm install
npm run dev          # 开发（默认代理到本机后端）
npm run build        # 产出 dist/，交给 Nginx 托管
```

## 本地验证

```bash
cd server/backend
python -m pytest tests -q
python -m compileall -q .

cd ../web
npm test
npm run build
```

## 生产部署要点

1. 设置 `ENVIRONMENT=production`。生产启动会拒绝默认 JWT secret、缺 SMTP 或通配 CORS。
2. 使用专用系统用户（如 `videomind`）和受限数据目录，不要用 root 跑服务。
3. 复制 `deploy/` 下的 systemd / Nginx 模板，把 `your-domain.com` 换成你的实际域名后再启用。
4. 证书：`deploy/README.md` 有 certbot 签发与自动续期步骤（IP 证书或域名证书按需选择）。
5. 上线前确认没有把 `.env` / 真实 Key / 数据库带入版本库。
6. 重启 API 与 Worker 后，验证 `/api/v1/health`、登录、任务归属、上传大小限制与 Worker 槽位。

## 关键环境变量

| 变量 | 说明 |
| :--- | :--- |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` | 上游端点与密钥（必填，无默认值） |
| `DEFAULT_MODEL` | 默认理解模型；**必须支持原生视频理解**，推荐 Gemini 系列 |
| `SECRET_KEY` | JWT 与验证码签名密钥（生产必填且非默认） |
| `DATABASE_URL` | 默认 `sqlite:///./jobs_data/app.sqlite3` |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | 邮箱验证码发信（生产必填） |
| `ADMIN_EMAIL` | 授予管理员角色的邮箱；留空则关闭管理后台 |
| `WORKER_COUNT` | Worker 并发槽位 |
| `MAX_VIDEO_DURATION_SEC` | 单视频时长上限（默认 14400 = 4 小时） |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔；生产不允许 `*` |

## 模型接入

VideoMind 不绑定模型供应商，`OPENAI_BASE_URL` 指向哪家由你决定：

- **官方 API（推荐用于生产）**：直接用 Google Gemini 官方端点，稳定性与数据合规性最有保障。
- **作者自营中转站**：`https://1127666.xyz` 是项目作者自营的中转服务（推广性质，非中立推荐），
  提供 Gemini 系列模型，价格约为官方定价的 1/5。使用前请注意：视频内容与 API Key 会经过该中转站，
  敏感数据场景请改用官方 API。换成其他兼容端点无需改动代码。

无论选哪种，都要确认所选模型支持**原生视频输入**（画面 + 音频），否则任务会直接失败。

## 许可

MIT，见仓库根目录 `LICENSE`。
