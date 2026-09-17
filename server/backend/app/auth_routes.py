import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, get_auth_context, require_user
from app.email_smtp import send_verification_email
from app.models import EmailCode, User, utcnow
from app.schemas import (
    PasswordLoginBody,
    RegisterBody,
    RequestCodeBody,
    RequestResetCodeBody,
    ResetPasswordBody,
    VerifyCodeBody,
)
from app.security import (
    create_access_token,
    generate_code,
    hash_code,
    hash_password,
    verify_code,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _check_cooldown(db: Session, email: str, now: dt.datetime) -> None:
    s = get_settings()
    latest = (
        db.query(EmailCode)
        .filter(EmailCode.email == email)
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if latest and latest.created_at:
        created = latest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=dt.timezone.utc)
        delta = (now - created).total_seconds()
        if delta < s.email_code_cooldown_seconds:
            wait = int(s.email_code_cooldown_seconds - delta)
            raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {wait} 秒后再试")


def _send_code(db: Session, email: str, purpose: str) -> str | None:
    """Generate, store, and send a verification code.
    Returns dev_code if SMTP not configured, else None.
    """
    s = get_settings()
    code = generate_code(s.email_code_length)
    now = utcnow()
    row = EmailCode(
        email=email,
        code_hash=hash_code(code, s.secret_key),
        purpose=purpose,
        expires_at=now + dt.timedelta(minutes=s.email_code_expire_minutes),
        consumed=False,
        created_at=now,
    )
    db.add(row)
    db.commit()

    try:
        send_verification_email(email, code)
    except Exception as e:
        is_dev = s.environment.strip().lower() not in {"production", "prod"}
        if is_dev and s.allow_dev_codes and not s.smtp_password:
            return code  # dev fallback
        raise HTTPException(status_code=503, detail=f"邮件发送失败: {e}") from e
    return None


# ---------------------------------------------------------------------------
# request verification code  (login / register / reset_password)
# ---------------------------------------------------------------------------

@router.post("/request-code")
def request_code(body: RequestCodeBody, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower().strip()
    purpose = (body.purpose or "login").strip()
    if purpose not in ("login", "register", "reset_password"):
        raise HTTPException(status_code=400, detail="purpose 必须是 login / register / reset_password")

    existing = db.query(User).filter(User.email == email).first()
    if purpose == "register":
        if existing:
            raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")
    else:
        if not existing:
            raise HTTPException(status_code=404, detail="该邮箱未注册，请先注册")

    _check_cooldown(db, email, utcnow())

    dev_code = _send_code(db, email, purpose)
    result: dict = {"ok": True, "cooldown": s.email_code_cooldown_seconds, "purpose": purpose}
    if dev_code:
        result["dev_code"] = dev_code
        result["warning"] = "SMTP 未配置，已返回 dev_code"
    return result


# ---------------------------------------------------------------------------
# code login for existing users only
# ---------------------------------------------------------------------------

@router.post("/verify")
def verify(body: VerifyCodeBody, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower().strip()
    code = body.code.strip()
    now = utcnow()
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册，请先注册")

    row = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.consumed.is_(False),
            EmailCode.purpose == "login",
        )
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="验证码无效或已使用")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp < now:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if not verify_code(code, row.code_hash, s.secret_key):
        raise HTTPException(status_code=400, detail="验证码错误")

    row.consumed = True
    db.commit()
    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "tier": user.tier},
        "has_password": bool(user.password_hash),
    }


# ---------------------------------------------------------------------------
# register with email + password + verification code
# ---------------------------------------------------------------------------

@router.post("/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower().strip()
    code = body.code.strip()
    password = body.password.strip()
    now = utcnow()

    # user must not exist
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")

    # verify code (purpose=register)
    row = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.purpose == "register",
            EmailCode.consumed.is_(False),
        )
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="验证码无效或已使用")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp < now:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if not verify_code(code, row.code_hash, s.secret_key):
        raise HTTPException(status_code=400, detail="验证码错误")

    row.consumed = True
    user = User(
        email=email,
        tier="user",
        password_hash=hash_password(password),
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "tier": user.tier},
        "has_password": True,
    }


# ---------------------------------------------------------------------------
# password login
# ---------------------------------------------------------------------------

@router.post("/login-password")
def login_password(body: PasswordLoginBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    password = body.password.strip()

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="该账户尚未设置密码，请使用验证码登录或通过找回密码设置密码")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "tier": user.tier},
        "has_password": True,
    }


# ---------------------------------------------------------------------------
# request reset password code
# ---------------------------------------------------------------------------

@router.post("/request-reset-code")
def request_reset_code(body: RequestResetCodeBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册")
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="该账户尚未设置密码，请使用验证码登录或通过找回密码设置密码")

    s = get_settings()
    _check_cooldown(db, email, utcnow())

    dev_code = _send_code(db, email, "reset_password")
    result: dict = {"ok": True, "cooldown": s.email_code_cooldown_seconds}
    if dev_code:
        result["dev_code"] = dev_code
        result["warning"] = "SMTP 未配置，已返回 dev_code"
    return result


# ---------------------------------------------------------------------------
# reset password
# ---------------------------------------------------------------------------

@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower().strip()
    code = body.code.strip()
    new_password = body.new_password.strip()
    now = utcnow()

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    row = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.purpose == "reset_password",
            EmailCode.consumed.is_(False),
        )
        .order_by(EmailCode.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="验证码无效或已使用")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp < now:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if not verify_code(code, row.code_hash, s.secret_key):
        raise HTTPException(status_code=400, detail="验证码错误")

    row.consumed = True
    user.password_hash = hash_password(new_password)
    db.commit()

    return {"ok": True, "message": "密码重置成功，请使用新密码登录"}


# ---------------------------------------------------------------------------
# set password when user only has verification-code login
# ---------------------------------------------------------------------------

@router.post("/set-password")
def set_password(
    body: ResetPasswordBody,  # reuse: email + code + new_password
    auth: AuthContext = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Logged-in user sets password for the first time (no code needed if already logged in)."""
    s = get_settings()
    email = body.email.lower().strip()
    new_password = body.new_password.strip()

    user = db.query(User).filter(User.id == auth.user.id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.email != email:
        raise HTTPException(status_code=403, detail="邮箱与当前用户不一致")

    # if user has no password, allow direct set; if has password, require code
    if user.password_hash:
        code = body.code.strip()
        row = (
            db.query(EmailCode)
            .filter(
                EmailCode.email == email,
                EmailCode.purpose == "reset_password",
                EmailCode.consumed.is_(False),
            )
            .order_by(EmailCode.created_at.desc())
            .first()
        )
        if not row:
            raise HTTPException(status_code=400, detail="验证码无效或已使用")
        if not verify_code(code, row.code_hash, s.secret_key):
            raise HTTPException(status_code=400, detail="验证码错误")
        row.consumed = True

    user.password_hash = hash_password(new_password)
    db.commit()
    return {"ok": True, "message": "密码设置成功"}


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------

@router.get("/me")
def me(auth: AuthContext = Depends(require_user)):
    u = auth.user
    return {
        "id": u.id,
        "email": u.email,
        "tier": u.tier,
        "role": getattr(u, "role", "user"),
        "via": auth.via,
        "has_password": bool(u.password_hash),
    }
