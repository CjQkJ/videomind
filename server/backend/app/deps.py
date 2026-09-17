from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApiKey, User
from app.security import decode_access_token, hash_api_key
from app.models import utcnow

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: Optional[User]
    via: str  # guest | jwt | api_key

    @property
    def user_id(self) -> Optional[int]:
        return self.user.id if self.user else None

    @property
    def tier(self) -> Optional[str]:
        return self.user.tier if self.user else None

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None


def get_auth_context(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    token = None
    if creds and creds.credentials:
        token = creds.credentials.strip()
    else:
        # also allow query for rare cases — prefer header only
        token = None

    if not token:
        return AuthContext(user=None, via="guest")

    if token.startswith("vw_"):
        h = hash_api_key(token)
        row = db.query(ApiKey).filter(ApiKey.key_hash == h, ApiKey.is_active.is_(True)).first()
        if not row:
            raise HTTPException(status_code=401, detail="无效的 API Key")
        user = db.query(User).filter(User.id == row.user_id, User.is_active.is_(True)).first()
        if not user:
            raise HTTPException(status_code=401, detail="API Key 所属用户不可用")
        row.last_used_at = utcnow()
        db.commit()
        return AuthContext(user=user, via="api_key")

    try:
        payload = decode_access_token(token)
        uid = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="无效或过期的登录凭证")
    user = db.query(User).filter(User.id == uid, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    _maybe_promote_admin(db, user)
    return AuthContext(user=user, via="jwt")


def require_user(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.is_authenticated:
        raise HTTPException(status_code=401, detail="需要登录或 API Key")
    return auth



def _maybe_promote_admin(db: Session, user: User) -> None:
    admin_email = get_settings().admin_email.lower().strip()
    if admin_email and user.email == admin_email and getattr(user, "role", None) != "admin":
        user.role = "admin"
        db.commit()


def require_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    auth = require_user(auth)
    if not auth.user or getattr(auth.user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return auth
