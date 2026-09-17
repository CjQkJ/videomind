"""Admin-only management endpoints. Every route requires require_admin."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, require_admin
from app.models import ApiKey, AppSetting, JobRow, User, utcnow
from app.runtime_config import effective_default_model, set_default_model

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class UserPatchBody(BaseModel):
    tier: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ApiKeyPatchBody(BaseModel):
    is_active: Optional[bool] = None


class SettingsPatchBody(BaseModel):
    default_model: Optional[str] = None


def _user_to_dict(u: User, job_count: int = 0, key_count: int = 0) -> Dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "tier": u.tier,
        "role": getattr(u, "role", "user"),
        "is_active": u.is_active,
        "has_password": bool(u.password_hash),
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "job_count": job_count,
        "api_key_count": key_count,
    }


def _job_to_dict(row: JobRow, email: Optional[str]) -> Dict[str, Any]:
    return {
        "job_id": row.job_id,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress or 0,
        "mode": row.mode or "study_note",
        "user_id": row.user_id,
        "user_email": email,
        "input_type": row.input_type,
        "input_url": row.input_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "error": row.error,
    }


def _key_to_dict(k: ApiKey, email: Optional[str]) -> Dict[str, Any]:
    return {
        "id": k.id,
        "user_id": k.user_id,
        "user_email": email,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
    }


@router.get("/stats")
def stats(auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    job_counts = {r[0]: r[1] for r in db.query(JobRow.status, func.count(JobRow.id)).group_by(JobRow.status).all()}
    return {
        "users": {
            "total": db.query(func.count(User.id)).scalar() or 0,
            "active": db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0,
            "admins": db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0,
        },
        "jobs": {
            "total": db.query(func.count(JobRow.id)).scalar() or 0,
            "today": db.query(func.count(JobRow.id)).filter(JobRow.created_at >= today_start).scalar() or 0,
            "running": job_counts.get("running", 0),
            "queued": job_counts.get("queued", 0),
            "succeeded": job_counts.get("succeeded", 0),
            "failed": job_counts.get("failed", 0),
        },
        "api_keys": {
            "total": db.query(func.count(ApiKey.id)).scalar() or 0,
            "active": db.query(func.count(ApiKey.id)).filter(ApiKey.is_active.is_(True)).scalar() or 0,
        },
        "default_model": effective_default_model(),
    }


@router.get("/users")
def list_users(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    qs = q.strip()
    if qs:
        query = query.filter(User.email.ilike("%" + qs + "%"))
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    ids = [r.id for r in rows]
    job_counts = {r[0]: r[1] for r in db.query(JobRow.user_id, func.count(JobRow.id)).filter(JobRow.user_id.in_(ids)).group_by(JobRow.user_id).all()} if ids else {}
    key_counts = {r[0]: r[1] for r in db.query(ApiKey.user_id, func.count(ApiKey.id)).filter(ApiKey.user_id.in_(ids)).group_by(ApiKey.user_id).all()} if ids else {}
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_user_to_dict(r, job_counts.get(r.id, 0), key_counts.get(r.id, 0)) for r in rows],
    }


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatchBody, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(404, "用户不存在")
    if body.tier is not None:
        if body.tier not in ("user", "vip"):
            raise HTTPException(400, "tier 必须是 user / vip")
        row.tier = body.tier
    if body.role is not None:
        if body.role not in ("user", "admin"):
            raise HTTPException(400, "role 必须是 user / admin")
        # do not let the sole admin demote themselves into a lockout silently
        row.role = body.role
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    db.commit()
    return _user_to_dict(row)


@router.get("/jobs")
def list_jobs(
    status: str = Query(""),
    email: str = Query(""),
    mode: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(JobRow, User.email).outerjoin(User, JobRow.user_id == User.id)
    if status.strip():
        query = query.filter(JobRow.status == status.strip())
    if mode.strip():
        query = query.filter(JobRow.mode == mode.strip())
    if email.strip():
        query = query.filter(User.email.ilike("%" + email.strip() + "%"))
    total = query.count()
    rows = query.order_by(JobRow.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_job_to_dict(r, em) for (r, em) in rows],
    }


@router.get("/api-keys")
def list_api_keys(
    email: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ApiKey, User.email).outerjoin(User, ApiKey.user_id == User.id)
    if email.strip():
        query = query.filter(User.email.ilike("%" + email.strip() + "%"))
    total = query.count()
    rows = query.order_by(ApiKey.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_key_to_dict(k, em) for (k, em) in rows],
    }


@router.patch("/api-keys/{key_id}")
def patch_api_key(key_id: int, body: ApiKeyPatchBody, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(404, "API Key 不存在")
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    db.commit()
    em = db.query(User.email).filter(User.id == row.user_id).scalar()
    return _key_to_dict(row, em)


@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(404, "API Key 不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/settings")
def get_admin_settings(auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    from app.config import get_settings
    s = get_settings()
    return {
        "default_model": effective_default_model(),
        "configured_model": s.default_model,
        "concurrency": {
            "guest_global": s.guest_global_concurrency,
            "user": s.user_concurrency,
            "vip": s.vip_concurrency,
            "global_hard_cap": s.global_hard_cap,
            "guest_queue_limit": s.guest_queue_limit,
            "user_queue_limit": s.user_queue_limit,
            "global_queue_limit": s.global_queue_limit,
        },
        "worker_count": s.worker_count,
        "understand_mode": s.understand_mode,
        "note": "default_model 修改后对新任务立即生效；并发上限与 worker_count 需修改环境变量并重启 worker 服务后生效。",
    }


@router.patch("/settings")
def patch_admin_settings(body: SettingsPatchBody, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    if body.default_model is not None:
        model = body.default_model.strip()
        if not model:
            raise HTTPException(400, "default_model 不能为空")
        set_default_model(model)
    return {"ok": True, "default_model": effective_default_model()}
