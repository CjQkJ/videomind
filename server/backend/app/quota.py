from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import JobRow


def concurrency_limit(tier: Optional[str], is_authenticated: bool) -> int:
    s = get_settings()
    if not is_authenticated:
        return s.guest_global_concurrency
    if (tier or "").lower() == "vip":
        return s.vip_concurrency
    return s.user_concurrency


def count_running_global(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(JobRow).where(JobRow.status == "running")) or 0
    )


def count_running_guests(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(JobRow)
            .where(JobRow.status == "running", JobRow.user_id.is_(None))
        )
        or 0
    )


def count_running_user(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(JobRow)
            .where(JobRow.status == "running", JobRow.user_id == user_id)
        )
        or 0
    )


def count_queued_global(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(JobRow).where(JobRow.status == "queued")) or 0
    )


def count_queued_guests(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(JobRow)
            .where(JobRow.status == "queued", JobRow.user_id.is_(None))
        )
        or 0
    )


def count_queued_user(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(JobRow)
            .where(JobRow.status == "queued", JobRow.user_id == user_id)
        )
        or 0
    )


def can_enqueue_job(db: Session, user_id: Optional[int]) -> Tuple[bool, str]:
    s = get_settings()
    if count_queued_global(db) >= s.global_queue_limit:
        return False, "global_queue_limit"
    if user_id is None:
        if count_queued_guests(db) >= s.guest_queue_limit:
            return False, "guest_queue_limit"
    elif count_queued_user(db, user_id) >= s.user_queue_limit:
        return False, "user_queue_limit"
    return True, "ok"


def can_start_job(
    db: Session,
    user_id: Optional[int],
    tier: Optional[str],
) -> Tuple[bool, str]:
    """Return (ok, reason). reason is 'ok' or a machine code."""
    s = get_settings()
    running_global = count_running_global(db)
    if running_global >= s.global_hard_cap:
        return False, "global_hard_cap"

    if user_id is None:
        if count_running_guests(db) >= s.guest_global_concurrency:
            return False, "guest_queue"
        return True, "ok"

    lim = concurrency_limit(tier, True)
    if count_running_user(db, user_id) >= lim:
        return False, "user_concurrency"
    return True, "ok"


def quota_snapshot(db: Session, user_id: Optional[int], tier: Optional[str]) -> dict:
    s = get_settings()
    is_auth = user_id is not None
    lim = concurrency_limit(tier if is_auth else None, is_auth)
    if user_id is None:
        running = count_running_guests(db)
        tier_name = "guest"
    else:
        running = count_running_user(db, user_id)
        tier_name = (tier or "user").lower()
    return {
        "tier": tier_name,
        "running": running,
        "limit": lim,
        "global_running": count_running_global(db),
        "global_limit": s.global_hard_cap,
    }
