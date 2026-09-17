#!/usr/bin/env bash
set -Eeuo pipefail

release_dir=${1:?usage: apply_release.sh RELEASE_DIR BACKUP_DIR RELEASE_ID}
backup_dir=${2:?usage: apply_release.sh RELEASE_DIR BACKUP_DIR RELEASE_ID}
release_id=${3:?usage: apply_release.sh RELEASE_DIR BACKUP_DIR RELEASE_ID}
app_root=/opt/video_workbench

case "$release_dir" in
  /opt/video_workbench/.deploy/*) ;;
  *) printf '%s\n' "unsafe release path: $release_dir" >&2; exit 2 ;;
esac
case "$backup_dir" in
  /opt/video_workbench/backups/*) ;;
  *) printf '%s\n' "unsafe backup path: $backup_dir" >&2; exit 2 ;;
esac
case "$release_id" in
  *[!A-Za-z0-9_-]*|'') printf '%s\n' "unsafe release id: $release_id" >&2; exit 2 ;;
esac

test -f "$release_dir/backend/main.py"
test -f "$release_dir/web/dist/index.html"
test -f "$release_dir/deploy/video_workbench.service"
test -f "$release_dir/deploy/nginx-video_workbench-http.conf"
test -f "$release_dir/deploy/nginx-video_workbench-https.conf"
test -f "$release_dir/deploy/videomind-certbot-renew.service"
test -f "$release_dir/deploy/videomind-certbot-renew.timer"
test -f "$backup_dir/code.tgz"
test -f "$backup_dir/app.sqlite3"
test -f "$backup_dir/env"

certificate=/etc/letsencrypt/live/your-domain.com/fullchain.pem
private_key=/etc/letsencrypt/live/your-domain.com/privkey.pem
nginx_release_conf="$release_dir/deploy/nginx-video_workbench-https.conf"
tls_enabled=true
if [ -s "$certificate" ] && [ -s "$private_key" ] && \
   openssl x509 -checkend 86400 -noout -in "$certificate" >/dev/null 2>&1 && \
   openssl pkey -check -noout -in "$private_key" >/dev/null 2>&1; then
  :
elif [ "${VIDEOMIND_ALLOW_HTTP_BOOTSTRAP:-0}" = 1 ]; then
  printf '%s\n' "WARNING: explicit HTTP bootstrap enabled; TLS is not active" >&2
  nginx_release_conf="$release_dir/deploy/nginx-video_workbench-http.conf"
  tls_enabled=false
else
  printf '%s\n' "refusing deployment: valid TLS certificate and key with at least 24h remaining are required" >&2
  printf '%s\n' "set VIDEOMIND_ALLOW_HTTP_BOOTSTRAP=1 only for first certificate issuance" >&2
  exit 5
fi

active_jobs=$(python3 - "$app_root/backend/jobs_data/app.sqlite3" <<'PY'
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], timeout=10)
count = connection.execute(
    "select count(1) from jobs where status in ('queued', 'running')"
).fetchone()[0]
connection.close()
print(count)
PY
)
if [ "$active_jobs" != "0" ]; then
  printf '%s\n' "refusing deployment with active jobs: $active_jobs" >&2
  exit 4
fi

rollback() {
  status=$?
  trap - ERR
  set +e
  printf '%s\n' "deployment failed; restoring $backup_dir" >&2
  systemctl stop video_workbench_worker.service video_workbench.service
  tar -xzf "$backup_dir/code.tgz" -C "$app_root"
  install -m 600 "$backup_dir/env" "$app_root/backend/.env"
  install -m 644 "$backup_dir/video_workbench.service" /etc/systemd/system/video_workbench.service
  install -m 644 "$backup_dir/video_workbench_worker.service" /etc/systemd/system/video_workbench_worker.service
  install -m 644 "$backup_dir/video_workbench_worker_2.service" /etc/systemd/system/video_workbench_worker_2.service
  install -m 644 "$backup_dir/nginx-video_workbench.conf" /etc/nginx/sites-available/video_workbench
  install -m 644 "$backup_dir/app.sqlite3" "$app_root/backend/jobs_data/app.sqlite3"
  systemctl daemon-reload
  systemctl enable video_workbench.service video_workbench_worker.service video_workbench_worker_2.service
  systemctl restart video_workbench.service video_workbench_worker.service video_workbench_worker_2.service
  nginx -t && systemctl reload nginx.service
  exit "$status"
}
trap rollback ERR

if ! id -u videomind >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/videomind --create-home --shell /usr/sbin/nologin videomind
fi
install -d -o videomind -g videomind -m 750 /var/lib/videomind

systemctl stop video_workbench_worker_2.service video_workbench_worker.service video_workbench.service

install -d -m 755 "$app_root/backend/app" "$app_root/backend/scripts" "$app_root/backend/templates" "$app_root/backend/tests"
cp -a "$release_dir/backend/app/." "$app_root/backend/app/"
cp -a "$release_dir/backend/scripts/." "$app_root/backend/scripts/"
cp -a "$release_dir/backend/templates/." "$app_root/backend/templates/"
cp -a "$release_dir/backend/tests/." "$app_root/backend/tests/"
install -m 644 "$release_dir/backend/main.py" "$app_root/backend/main.py"
install -m 644 "$release_dir/backend/pipeline.py" "$app_root/backend/pipeline.py"
install -m 644 "$release_dir/backend/requirements.txt" "$app_root/backend/requirements.txt"

install -d -m 755 "$app_root/web" "$app_root/web/src" "$app_root/web/tests" "$app_root/web/public"
cp -a "$release_dir/web/src/." "$app_root/web/src/"
cp -a "$release_dir/web/tests/." "$app_root/web/tests/"
cp -a "$release_dir/web/public/." "$app_root/web/public/"
for name in index.html package.json package-lock.json tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts README.md; do
  install -m 644 "$release_dir/web/$name" "$app_root/web/$name"
done

new_dist="$app_root/web/dist.release_$release_id"
old_dist="$app_root/web/dist.rollback_$release_id"
test ! -e "$new_dist"
test ! -e "$old_dist"
cp -a "$release_dir/web/dist" "$new_dist"
if [ -d "$app_root/web/dist" ]; then
  mv "$app_root/web/dist" "$old_dist"
fi
mv "$new_dist" "$app_root/web/dist"

install -d -m 755 "$app_root/docs" "$app_root/deploy" "$app_root/frontend"
cp -a "$release_dir/docs/." "$app_root/docs/"
cp -a "$release_dir/deploy/." "$app_root/deploy/"
install -m 644 "$release_dir/frontend/index.html" "$app_root/frontend/index.html"
install -m 644 "$release_dir/README.md" "$app_root/README.md"

chown -R root:root "$app_root/backend/app" "$app_root/backend/scripts" "$app_root/backend/templates" "$app_root/backend/tests" "$app_root/web" "$app_root/docs" "$app_root/deploy" "$app_root/frontend"
find "$app_root/backend/app" "$app_root/backend/scripts" "$app_root/backend/templates" "$app_root/backend/tests" "$app_root/web" "$app_root/docs" "$app_root/deploy" "$app_root/frontend" -type d -exec chmod 755 {} +
find "$app_root/backend/app" "$app_root/backend/scripts" "$app_root/backend/templates" "$app_root/backend/tests" "$app_root/web" "$app_root/docs" "$app_root/deploy" "$app_root/frontend" -type f -exec chmod 644 {} +

install -d -o videomind -g videomind -m 750 "$app_root/backend/jobs_data" "$app_root/backend/uploads_data"
chown -R videomind:videomind "$app_root/backend/jobs_data" "$app_root/backend/uploads_data"
find "$app_root/backend/jobs_data" "$app_root/backend/uploads_data" -type d -exec chmod 750 {} +
find "$app_root/backend/jobs_data" "$app_root/backend/uploads_data" -type f -exec chmod 640 {} +

env_tmp=$(mktemp "$app_root/backend/.env.XXXXXX")
awk -F= '!/^(ENVIRONMENT|ALLOW_DEV_CODES|CORS_ORIGINS|MAX_UPLOAD_SIZE_BYTES|GUEST_QUEUE_LIMIT|USER_QUEUE_LIMIT|GLOBAL_QUEUE_LIMIT|WORKER_COUNT|WORKER_LEASE_SECONDS)=/' "$app_root/backend/.env" > "$env_tmp"
printf '%s\n' \
  'ENVIRONMENT=production' \
  'ALLOW_DEV_CODES=false' \
  'CORS_ORIGINS=' \
  'MAX_UPLOAD_SIZE_BYTES=524288000' \
  'GUEST_QUEUE_LIMIT=10' \
  'USER_QUEUE_LIMIT=20' \
  'GLOBAL_QUEUE_LIMIT=200' \
  'WORKER_COUNT=2' \
  'WORKER_LEASE_SECONDS=3600' >> "$env_tmp"
chown root:videomind "$env_tmp"
chmod 640 "$env_tmp"
mv "$env_tmp" "$app_root/backend/.env"

install -m 644 "$release_dir/deploy/video_workbench.service" /etc/systemd/system/video_workbench.service
install -m 644 "$release_dir/deploy/video_workbench_worker.service" /etc/systemd/system/video_workbench_worker.service

if [ "$tls_enabled" = true ]; then
  install -m 644 "$release_dir/deploy/videomind-certbot-renew.service" /etc/systemd/system/videomind-certbot-renew.service
  install -m 644 "$release_dir/deploy/videomind-certbot-renew.timer" /etc/systemd/system/videomind-certbot-renew.timer
fi
install -m 644 "$nginx_release_conf" /etc/nginx/sites-available/video_workbench

systemctl daemon-reload
systemctl disable video_workbench_worker_2.service
systemctl enable video_workbench.service video_workbench_worker.service
if [ "$tls_enabled" = true ]; then
  systemctl enable --now videomind-certbot-renew.timer
fi
nginx -t

cd "$app_root/backend"
runuser -u videomind -- env DATABASE_URL=sqlite:////opt/video_workbench/backend/jobs_data/app.sqlite3 PYTHONDONTWRITEBYTECODE=1 python3 scripts/sanitize_job_secrets.py
runuser -u videomind -- env DATABASE_URL=sqlite:////opt/video_workbench/backend/jobs_data/app.sqlite3 PYTHONDONTWRITEBYTECODE=1 python3 scripts/sanitize_job_secrets.py --apply

systemctl start video_workbench.service
for _ in $(seq 1 20); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/api/v1/health >/dev/null; then
    break
  fi
  sleep 1
done
curl -fsS --max-time 5 http://127.0.0.1:8000/api/v1/health >/dev/null
systemctl start video_workbench_worker.service
systemctl reload nginx.service

trap - ERR
printf '%s\n' "DEPLOY_OK release=$release_id"
