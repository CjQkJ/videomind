import datetime as dt
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from app import quota, worker
from app.db import Base
from app.deps import AuthContext
from app.models import JobRow, UploadRow, User, utcnow
from app.schemas import CreateJobRequest


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_guest_queue_limit_rejects_new_job(db, tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    jobs_dir = tmp_path / "jobs"
    uploads_dir.mkdir()
    jobs_dir.mkdir()
    monkeypatch.setattr(main, "UPLOADS_DIR", str(uploads_dir))
    monkeypatch.setattr(main, "JOBS_DIR", str(jobs_dir))

    settings = main.get_settings()
    values = settings.model_dump()
    values.update(guest_queue_limit=2, user_queue_limit=4, global_queue_limit=6)
    limited = SimpleNamespace(**values)
    monkeypatch.setattr(quota, "get_settings", lambda: limited)

    for index in range(2):
        db.add(
            JobRow(
                job_id=f"job_queued_{index}",
                user_id=None,
                status="queued",
                mode="study_note",
            )
        )
    file_id = "guest_input.mp4"
    (uploads_dir / file_id).write_bytes(b"x" * 2048)
    db.add(
        UploadRow(
            file_id=file_id,
            user_id=None,
            original_filename="guest_input.mp4",
            size_bytes=2048,
        )
    )
    db.commit()

    request = CreateJobRequest.model_validate(
        {
            "input": {"type": "upload", "file_id": file_id},
            "output": {"mode": "study_note"},
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        main.create_job(request, AuthContext(user=None, via="guest"), db)

    assert exc_info.value.status_code == 429
    assert db.query(JobRow).filter(JobRow.status == "queued").count() == 2


def test_recover_stale_running_jobs_requeues_expired_lease(db):
    stale = JobRow(
        job_id="job_stale_worker",
        user_id=None,
        status="running",
        stage="ai_extraction",
        message="old worker",
        started_at=utcnow() - dt.timedelta(hours=2),
        updated_at=utcnow() - dt.timedelta(hours=2),
    )
    fresh = JobRow(
        job_id="job_fresh_worker",
        user_id=None,
        status="running",
        stage="download",
        message="active worker",
        started_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add_all([stale, fresh])
    db.commit()

    recovered = worker.recover_stale_jobs(db, lease_seconds=3600)

    db.refresh(stale)
    db.refresh(fresh)
    assert recovered == 1
    assert stale.status == "queued"
    assert stale.stage == "queued"
    assert stale.started_at is None
    assert fresh.status == "running"


def test_claim_jobs_for_capacity_uses_configured_worker_slots(db):
    user = User(email="worker-slots@example.com", tier="user", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    for index in range(3):
        db.add(
            JobRow(
                job_id=f"job_worker_slot_{index}",
                user_id=user.id,
                status="queued",
                mode="study_note",
            )
        )
    db.commit()

    claimed = worker.claim_jobs_for_capacity(db, slots=2)

    assert len(claimed) == 2
    assert db.query(JobRow).filter(JobRow.status == "running").count() == 2
    assert db.query(JobRow).filter(JobRow.status == "queued").count() == 1
