"""Video Workbench API — multi-user product entrypoint."""
from __future__ import annotations

import os
import re
import uuid
import json
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api_key_routes import router as api_key_router
from app.auth_routes import router as auth_router
from app.admin_routes import router as admin_router
from app.config import get_settings, validate_runtime_security
from app.db import get_db, init_db
from app.deps import AuthContext, get_auth_context, require_user
from app.models import JobRow, UploadRow, utcnow
from app.quota import can_enqueue_job, can_start_job, quota_snapshot
from app.schemas import CreateJobRequest, RerenderRequest
from pipeline import normalize_bilibili_url, render_mode, UNDERSTAND_MODE, DEFAULT_MODEL

settings = get_settings()
JOBS_DIR = settings.jobs_dir
UPLOADS_DIR = settings.uploads_dir
os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Keep pipeline env defaults aligned
os.environ.setdefault("JOBS_DIR", os.path.abspath(JOBS_DIR))
os.environ.setdefault("UPLOADS_DIR", os.path.abspath(UPLOADS_DIR))

app = FastAPI(title="VideoMind Workbench API", version="2.0.0")
cors_origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(auth_router)
app.include_router(api_key_router)
app.include_router(admin_router)

ALLOWED_MODES = {"study_note", "article", "cards", "teaching_html"}
ALLOWED_INPUT_TYPES = {"bilibili_url", "upload"}
JOB_ID_RE = re.compile(r"^job_[A-Za-z0-9_-]{1,59}$")


@app.on_event("startup")
def on_startup():
    validate_runtime_security(get_settings())
    init_db()


def job_to_dict(row: JobRow) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "job_id": row.job_id,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress or 0,
        "message": row.message or "",
        "mode": row.mode or "study_note",
        "user_id": row.user_id,
        "segment_total": row.segment_total or 0,
        "segment_done": row.segment_done or 0,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if row.error:
        d["error"] = row.error
    if row.metadata_json:
        meta = dict(row.metadata_json)
        meta.pop("local_video_path", None)
        d["metadata"] = meta
    if row.options_json:
        opts = dict(row.options_json)
        if opts.get("api_key"):
            k = str(opts["api_key"])
            opts["api_key"] = (k[:6] + "..." + k[-4:]) if len(k) > 12 else "***"
        d["options"] = opts
    return d


def validate_job_id(job_id: str) -> str:
    if not JOB_ID_RE.fullmatch(job_id or ""):
        raise HTTPException(400, "非法 job_id")
    return job_id


def require_job_read_access(row: Optional[JobRow], auth: AuthContext) -> None:
    if row and row.user_id is not None and row.user_id != auth.user_id:
        raise HTTPException(403, "无权查看该任务")


def require_job_write_access(row: Optional[JobRow], auth: AuthContext) -> JobRow:
    if not row:
        raise HTTPException(404, "Job not found")
    if not auth.is_authenticated or row.user_id is None or row.user_id != auth.user_id:
        raise HTTPException(403, "无权修改该任务")
    return row


def job_artifact_path(job_id: str, filename: str) -> str:
    validate_job_id(job_id)
    jobs_root = os.path.abspath(JOBS_DIR)
    path = os.path.abspath(os.path.join(jobs_root, job_id, filename))
    if os.path.commonpath([jobs_root, path]) != jobs_root:
        raise HTTPException(400, "非法任务路径")
    return path


def validate_create(
    req: CreateJobRequest,
    auth: AuthContext,
    db: Session,
) -> CreateJobRequest:
    if req.input.type not in ALLOWED_INPUT_TYPES:
        raise HTTPException(400, f"input.type 必须是 {sorted(ALLOWED_INPUT_TYPES)}")
    mode = (req.output.mode if req.output and req.output.mode else None) or req.mode or "study_note"
    if mode not in ALLOWED_MODES:
        raise HTTPException(400, f"mode 必须是 {sorted(ALLOWED_MODES)}")
    if req.output is None:
        from app.schemas import JobOutput

        req.output = JobOutput(mode=mode)
    else:
        req.output.mode = mode
    if req.input.type == "bilibili_url":
        url = (req.input.url or "").strip()
        if not url:
            raise HTTPException(400, "bilibili_url 类型必须提供 url")
        try:
            normalized = normalize_bilibili_url(url)
        except Exception as e:
            raise HTTPException(400, f"B站链接解析失败: {e}") from e
        if "bilibili.com" not in normalized and "b23.tv" not in normalized and "BV" not in normalized:
            raise HTTPException(400, "无法识别有效的 B 站链接/BV 号/b23 短链")
        req.input.url = normalized
    else:
        file_id = (req.input.file_id or "").strip()
        if not file_id or "/" in file_id or "\\" in file_id or ".." in file_id:
            raise HTTPException(400, "非法 file_id")
        path = os.path.join(UPLOADS_DIR, file_id)
        if not os.path.exists(path):
            raise HTTPException(404, f"上传文件不存在: {file_id}")
        upload = db.query(UploadRow).filter(UploadRow.file_id == file_id).first()
        if not upload:
            raise HTTPException(400, "上传文件未登记，请重新上传")
        if upload.user_id != auth.user_id:
            raise HTTPException(403, "无权使用该上传文件")
        req.input.file_id = file_id
    return req


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth_context)):
    s = get_settings()
    return {
        "status": "ok",
        "version": "2.0.0",
        "understand_mode": s.understand_mode or UNDERSTAND_MODE,
        "default_model": s.default_model or DEFAULT_MODEL,
        "max_video_duration_sec": s.max_video_duration_sec,
        "worker_count": s.worker_count,
        "quota_defaults": {
            "guest": s.guest_global_concurrency,
            "user": s.user_concurrency,
            "vip": s.vip_concurrency,
            "global_hard_cap": s.global_hard_cap,
        },
        "quota": quota_snapshot(db, auth.user_id, auth.tier),
    }


@app.post("/api/v1/uploads")
async def upload_file(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    lower = file.filename.lower()
    if not any(lower.endswith(ext) for ext in (".mp4", ".mov", ".mkv", ".webm", ".m4v")):
        raise HTTPException(400, "仅支持视频文件（mp4/mov/mkv/webm/m4v）")
    safe_name = re.sub(r"[^\w.\-()\u4e00-\u9fff \[\]]+", "_", file.filename)
    file_id = f"{uuid.uuid4().hex}_{safe_name}"
    path = os.path.join(UPLOADS_DIR, file_id)
    max_bytes = int(getattr(get_settings(), "max_upload_size_bytes", 500 * 1024 * 1024))
    size = 0
    try:
        with open(path, "wb") as buf:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"上传文件不能超过 {max_bytes} 字节")
                buf.write(chunk)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    if size < 1024:
        try:
            os.remove(path)
        except OSError:
            pass
        raise HTTPException(400, "上传文件过小或为空")
    db.add(
        UploadRow(
            file_id=file_id,
            user_id=auth.user_id,
            original_filename=file.filename,
            size_bytes=size,
        )
    )
    db.commit()
    return {"file_id": file_id, "filename": file.filename, "size": size}


@app.post("/api/v1/jobs")
def create_job(
    req: CreateJobRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    # API-only path: pure API callers should use key; guests allowed for web
    req = validate_create(req, auth, db)
    can_enqueue, enqueue_reason = can_enqueue_job(db, auth.user_id)
    if not can_enqueue:
        raise HTTPException(429, f"任务队列已满: {enqueue_reason}")
    mode = req.output.mode if req.output else (req.mode or "study_note")
    options = (req.options.model_dump() if req.options else {}) if hasattr(req.options or object(), "model_dump") else (
        req.options.dict() if req.options else {}
    )
    # Upstream routing and credentials are server-owned and never persisted per job.
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = utcnow()
    row = JobRow(
        job_id=job_id,
        user_id=auth.user_id,
        status="queued",
        stage="queued",
        progress=0,
        message="已排队，等待 Worker...",
        mode=mode,
        input_type=req.input.type,
        input_url=req.input.url,
        input_file_id=req.input.file_id,
        request_json=req.model_dump() if hasattr(req, "model_dump") else req.dict(),
        options_json=options,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()

    os.makedirs(os.path.join(JOBS_DIR, job_id), exist_ok=True)
    with open(os.path.join(JOBS_DIR, job_id, "status.json"), "w", encoding="utf-8") as f:
        json.dump(job_to_dict(row), f, ensure_ascii=False, indent=2, default=str)

    q = quota_snapshot(db, auth.user_id, auth.tier)
    # Informational: whether it can start immediately
    ok, reason = can_start_job(db, auth.user_id, auth.tier)
    return {
        "job_id": job_id,
        "status": "queued",
        "can_start_now": ok,
        "queue_reason": reason if not ok else "ok",
        "quota": q,
    }


@app.get("/api/v1/jobs")
def list_jobs(
    limit: int = 30,
    auth: AuthContext = Depends(require_user),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    rows = (
        db.query(JobRow)
        .filter(JobRow.user_id == auth.user_id)
        .order_by(JobRow.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [job_to_dict(r) for r in rows], "quota": quota_snapshot(db, auth.user_id, auth.tier)}


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    validate_job_id(job_id)
    row = db.query(JobRow).filter(JobRow.job_id == job_id).first()
    if not row:
        # disk recovery for legacy jobs
        disk = _load_disk_job(job_id)
        if not disk:
            raise HTTPException(404, "Job not found")
        out = disk
    else:
        require_job_read_access(row, auth)
        out = job_to_dict(row)
    out["quota"] = quota_snapshot(db, auth.user_id, auth.tier)
    return out


@app.get("/api/v1/jobs/{job_id}/result")
def get_job_result(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    validate_job_id(job_id)
    row = db.query(JobRow).filter(JobRow.job_id == job_id).first()
    require_job_read_access(row, auth)

    json_path = job_artifact_path(job_id, "result.json")
    md_path = job_artifact_path(job_id, "result.md")
    if os.path.exists(json_path) or os.path.exists(md_path):
        metadata = (row.metadata_json if row else None) or {}
        if not metadata and os.path.exists(json_path):
            try:
                data = json.load(open(json_path, encoding="utf-8"))
                src = data.get("source") or {}
                metadata = {
                    "title": src.get("title") or "未命名视频",
                    "uploader": src.get("uploader") or "未知",
                    "duration_sec": src.get("duration_sec") or 0,
                    "source_url": src.get("source_url") or "",
                }
            except Exception:
                metadata = {}
        return {
            "job_id": job_id,
            "status": "succeeded",
            "mode": (row.mode if row else "study_note"),
            "metadata": metadata,
            "artifacts": {
                "json_url": f"/api/v1/jobs/{job_id}/result.json",
                "markdown_url": f"/api/v1/jobs/{job_id}/result.md",
                "html_url": f"/api/v1/jobs/{job_id}/result.html",
            },
            "quota": quota_snapshot(db, auth.user_id, auth.tier),
        }
    if not row:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job_id,
        "status": row.status,
        "message": row.message,
        "error": row.error,
        "quota": quota_snapshot(db, auth.user_id, auth.tier),
    }


@app.get("/api/v1/jobs/{job_id}/result.json")
def get_result_json(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    row = db.query(JobRow).filter(JobRow.job_id == validate_job_id(job_id)).first()
    require_job_read_access(row, auth)
    path = job_artifact_path(job_id, "result.json")
    if not os.path.exists(path):
        raise HTTPException(404, "Result JSON not found")
    return FileResponse(path, media_type="application/json")


@app.get("/api/v1/jobs/{job_id}/result.md")
def get_result_md(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    row = db.query(JobRow).filter(JobRow.job_id == validate_job_id(job_id)).first()
    require_job_read_access(row, auth)
    path = job_artifact_path(job_id, "result.md")
    if not os.path.exists(path):
        raise HTTPException(404, "Result Markdown not found")
    return Response(open(path, encoding="utf-8").read(), media_type="text/markdown; charset=utf-8")


@app.get("/api/v1/jobs/{job_id}/result.html")
def get_result_html(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    row = db.query(JobRow).filter(JobRow.job_id == validate_job_id(job_id)).first()
    require_job_read_access(row, auth)
    path = job_artifact_path(job_id, "result.html")
    if not os.path.exists(path):
        raise HTTPException(404, "Result HTML not found")
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Content-Security-Policy": (
                "sandbox; default-src 'none'; style-src 'unsafe-inline'; "
                "img-src data: blob: https: http:; media-src data: blob: https: http:; "
                "font-src data: https: http:; connect-src 'none'; form-action 'none'; "
                "base-uri 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.post("/api/v1/jobs/{job_id}/rerender")
def rerender_job(
    job_id: str,
    body: RerenderRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    validate_job_id(job_id)
    if body.mode not in ALLOWED_MODES:
        raise HTTPException(400, f"mode 必须是 {sorted(ALLOWED_MODES)}")
    row = db.query(JobRow).filter(JobRow.job_id == job_id).first()
    require_job_write_access(row, auth)
    json_path = job_artifact_path(job_id, "result.json")
    if not os.path.exists(json_path):
        raise HTTPException(404, "Canonical JSON not found")
    data = json.load(open(json_path, encoding="utf-8"))
    from app.job_runner import _teaching_html

    if body.mode == "teaching_html":
        html = _teaching_html(data)
        open(job_artifact_path(job_id, "result.html"), "w", encoding="utf-8").write(html)
        md = render_mode(data, mode="teaching_html", show_source=bool(body.show_source))
    else:
        md = render_mode(data, mode=body.mode, show_source=bool(body.show_source))
    open(job_artifact_path(job_id, "result.md"), "w", encoding="utf-8").write(md)
    row.mode = body.mode
    row.updated_at = utcnow()
    db.commit()
    return {"status": "succeeded", "mode": body.mode, "markdown": md}


def _load_disk_job(job_id: str) -> Optional[Dict[str, Any]]:
    validate_job_id(job_id)
    job_dir = os.path.dirname(job_artifact_path(job_id, "status.json"))
    if not os.path.isdir(job_dir):
        return None
    status_path = os.path.join(job_dir, "status.json")
    out: Dict[str, Any] = {"job_id": job_id, "recovered_from_disk": True}
    if os.path.exists(status_path):
        try:
            out.update(json.load(open(status_path, encoding="utf-8")))
        except Exception:
            pass
    if os.path.exists(os.path.join(job_dir, "result.json")):
        out.update({"status": "succeeded", "stage": "completed", "progress": 100})
        if "metadata" not in out:
            try:
                data = json.load(open(os.path.join(job_dir, "result.json"), encoding="utf-8"))
                out["metadata"] = data.get("source") or {}
            except Exception:
                pass
    return out if out.get("status") or os.path.exists(os.path.join(job_dir, "result.json")) else None


# Static frontend: production must never fall back to the legacy unsanitized page.
_web_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/dist"))
_frontend = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.isdir(_web_dist):
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")
elif settings.environment.strip().lower() not in {"production", "prod"} and os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
