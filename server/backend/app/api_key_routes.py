from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, require_user
from app.models import ApiKey, utcnow
from app.schemas import ApiKeyCreate
from app.security import hash_api_key, new_api_key

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.post("")
def create_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(require_user),
    db: Session = Depends(get_db),
):
    raw = new_api_key()
    row = ApiKey(
        user_id=auth.user.id,
        name=(body.name or "default")[:128],
        key_prefix=raw[:10],
        key_hash=hash_api_key(raw),
        is_active=True,
        created_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "key": raw,  # only once
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "warning": "请立即保存，明文 Key 不会再次显示",
    }


@router.get("")
def list_keys(auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == auth.user.id)
        .order_by(ApiKey.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "key_prefix": r.key_prefix,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        }
        for r in rows
    ]


@router.delete("/{key_id}")
def delete_key(
    key_id: int,
    auth: AuthContext = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == auth.user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    row.is_active = False
    db.commit()
    return {"ok": True, "id": key_id}
