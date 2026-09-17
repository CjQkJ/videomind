# 生产部署模板

这些文件是部署 VideoMind 服务端的参考模板，**使用前请把 `your-domain.com` 替换成你的实际域名**（或 IP），并按需调整路径。

## 文件说明

| 文件 | 用途 |
| :--- | :--- |
| `video_workbench.service` | FastAPI 服务，监听回环地址，以专用用户运行 |
| `video_workbench_worker.service` | 任务 Worker 进程；`WORKER_COUNT` 控制实际并发槽位 |
| `nginx-video_workbench-http.conf` | 签发证书前的 HTTP 配置 |
| `nginx-video_workbench-https.conf` | HTTPS 配置（HTTP 入口 308 跳转） |
| `videomind-certbot-renew.service` / `.timer` | 证书自动续期（每 6 小时检查） |
| `apply_release.sh` | 发布脚本：校验证书有效期后切换配置，失败即中止 |

## 部署前准备

1. **备份**：如果是从既有部署升级，先备份代码目录、systemd 单元、Nginx 配置、`.env` 和 SQLite（含 WAL/SHM 文件）。
2. **创建目录**：
   ```bash
   mkdir -p /opt/video_workbench /var/www/letsencrypt
   mkdir -p /opt/video_workbench/backend/{jobs_data,uploads_data}
   ```
3. **专用用户**：建议创建 `videomind` 用户运行服务，并让数据目录归其所有，不要用 root。
4. **环境变量**：参照 `backend/.env.example` 生成 `.env`；生产环境必须设置 `ENVIRONMENT=production`、非默认 `SECRET_KEY` 和 SMTP 凭据。

## 证书签发

### 域名证书（推荐）

```bash
certbot certonly --webroot --webroot-path /var/www/letsencrypt -d your-domain.com
```

### IP 证书（无域名时）

IP 证书由 Let's Encrypt 短周期 profile 签发，有效期约 6 天，必须确保自动续期正常：

```bash
certbot certonly --preferred-profile shortlived --webroot \
  --webroot-path /var/www/letsencrypt --ip-address YOUR_SERVER_IP
```

> `--ip-address` 必须填 IP；使用域名证书时不要加这个参数。

验证续期（跳过随机延迟，便于测试）：

```bash
/opt/certbot-venv/bin/certbot renew --dry-run --no-random-sleep-on-renew \
  --cert-name your-domain.com \
  --deploy-hook "/usr/bin/systemctl reload nginx.service"
```

安装续期定时器：

```bash
cp videomind-certbot-renew.service videomind-certbot-renew.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now videomind-certbot-renew.timer
```

## 启用服务

```bash
cp video_workbench.service video_workbench_worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now video_workbench video_workbench_worker
```

Nginx：先把 `nginx-video_workbench-http.conf` 的 `server_name` 与证书路径改成你的实际值，`nginx -t` 通过后启用；证书就绪后再切换到 HTTPS 版本。

## 上线检查

- `curl https://your-domain.com/api/v1/health` 返回正常
- 证书有效期与 SAN 覆盖正确
- HTTP 入口正确 308 跳转到 HTTPS
- 登录、任务提交、任务归属隔离、上传大小限制、Worker 并发槽位均符合预期

## 发布脚本

`apply_release.sh` 会校验证书存在且剩余有效期不少于 24 小时，然后切换 Nginx 配置并启用续期定时器；校验失败则中止（fail closed）。

仅首次签发、尚无证书时可显式允许 HTTP 引导：

```bash
VIDEOMIND_ALLOW_HTTP_BOOTSTRAP=1 bash deploy/apply_release.sh RELEASE_DIR BACKUP_DIR RELEASE_ID
```

生产 TLS 建立后不要再设置该变量。
