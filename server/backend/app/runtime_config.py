"""Runtime-overridable settings backed by the app_settings table.

Lets the admin UI change high-leverage values (model name) at runtime.
Worker processes re-read on every job, so model-name changes take effect
for the next queued job immediately. Concurrency caps are read once at
worker startup, so those still need a worker restart.
"""
from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.db import SessionLocal
from app.models import AppSetting, utcnow

_MODEL_KEY = "default_model"


def _read(key: str) -> Optional[str]:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        return row.value if row else None
    finally:
        db.close()


def _write(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
            row.updated_at = utcnow()
        else:
            db.add(AppSetting(key=key, value=value, updated_at=utcnow()))
        db.commit()
    finally:
        db.close()


def effective_default_model() -> str:
    override = _read(_MODEL_KEY)
    if override and override.strip():
        return override.strip()
    return get_settings().default_model


def set_default_model(value: str) -> str:
    _write(_MODEL_KEY, value.strip())
    return effective_default_model()
