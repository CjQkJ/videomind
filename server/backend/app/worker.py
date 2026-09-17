"""DB-backed job worker process.

Run: python -m app.worker
"""
from __future__ import annotations

import os
import sys
import time
import traceback
import datetime as dt
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy import text

# ensure backend root on path
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.job_runner import run_job
from app.models import JobRow, utcnow
from app.quota import can_start_job
from app.models import User


def recover_stale_jobs(db, lease_seconds: int) -> int:
    """Requeue jobs whose worker lease has expired."""
    cutoff = utcnow() - dt.timedelta(seconds=max(1, int(lease_seconds)))
    rows = (
        db.query(JobRow)
        .filter(JobRow.status == "running", JobRow.updated_at < cutoff)
        .all()
    )
    now = utcnow()
    for row in rows:
        row.status = "queued"
        row.stage = "queued"
        row.message = "Worker 租约超时，任务已重新排队"
        row.started_at = None
        row.updated_at = now
    if rows:
        db.commit()
    return len(rows)


def claim_next_job(db) -> str | None:
    """Atomically claim one eligible queued job for this worker."""
    queued = (
        db.query(JobRow)
        .filter(JobRow.status == "queued")
        .order_by(JobRow.id.asc())
        .limit(50)
        .all()
    )
    for candidate in queued:
        tier = None
        if candidate.user_id:
            u = db.query(User).filter(User.id == candidate.user_id).first()
            tier = u.tier if u else "user"
        ok, _reason = can_start_job(db, candidate.user_id, tier)
        if not ok:
            continue

        # SQLite serializes this UPDATE; only one worker can change this row
        # from queued to running. A second worker will see rowcount == 0.
        now = utcnow()
        result = db.execute(
            text("""
                UPDATE jobs
                   SET status = :status,
                       stage = :stage,
                       message = :message,
                       started_at = :started_at,
                       updated_at = :updated_at
                 WHERE job_id = :job_id AND status = 'queued'
            """),
            {
                "status": "running",
                "stage": "queued",
                "message": "Worker 已领取任务",
                "started_at": now,
                "updated_at": now,
                "job_id": candidate.job_id,
            },
        )
        if result.rowcount == 1:
            db.commit()
            return candidate.job_id
        db.rollback()
    return None


def pick_next_job(db) -> str | None:
    """Backward-compatible alias for callers/tests."""
    return claim_next_job(db)


def claim_jobs_for_capacity(db, slots: int) -> list[str]:
    claimed: list[str] = []
    for _ in range(max(0, int(slots))):
        job_id = claim_next_job(db)
        if not job_id:
            break
        claimed.append(job_id)
    return claimed


def _run_job_logged(job_id: str) -> None:
    print(f"[worker] running {job_id}")
    try:
        run_job(job_id)
    except Exception:
        traceback.print_exc()
    print(f"[worker] finished {job_id}")


def main_loop():
    os.chdir(_BACKEND_ROOT)
    settings = get_settings()
    os.makedirs(settings.jobs_dir, exist_ok=True)
    os.makedirs(settings.uploads_dir, exist_ok=True)
    init_db()
    recovery_db = SessionLocal()
    try:
        recovered = recover_stale_jobs(recovery_db, settings.worker_lease_seconds)
        if recovered:
            print(f"[worker] requeued stale jobs={recovered}")
    finally:
        recovery_db.close()
    worker_count = max(1, int(settings.worker_count))
    print(
        f"[worker] started poll={settings.worker_poll_seconds}s "
        f"slots={worker_count} cwd={os.getcwd()}"
    )
    active: dict[Future, str] = {}
    last_recovery = 0.0
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="videomind") as pool:
        while True:
            for future in [item for item in active if item.done()]:
                job_id = active.pop(future)
                try:
                    future.result()
                except Exception:
                    print(f"[worker] unhandled failure {job_id}")
                    traceback.print_exc()

            # periodic lease recovery: self-heal orphaned 'running' jobs
            # (e.g. a thread that died without marking the job failed)
            if time.monotonic() - last_recovery >= 60:
                last_recovery = time.monotonic()
                recovery_db = SessionLocal()
                try:
                    recovered = recover_stale_jobs(recovery_db, settings.worker_lease_seconds)
                    if recovered:
                        print(f"[worker] requeued stale jobs={recovered}")
                except Exception:
                    traceback.print_exc()
                finally:
                    recovery_db.close()

            available = worker_count - len(active)
            claimed: list[str] = []
            if available > 0:
                db = SessionLocal()
                try:
                    claimed = claim_jobs_for_capacity(db, available)
                except Exception:
                    traceback.print_exc()
                finally:
                    db.close()
                for job_id in claimed:
                    active[pool.submit(_run_job_logged, job_id)] = job_id

            if not claimed:
                time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main_loop()
