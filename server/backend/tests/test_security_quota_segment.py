import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.security import generate_code, hash_code, verify_code, hash_api_key, new_api_key
from app.segment import plan_segments
from app.quota import concurrency_limit
from app.config import get_settings
from app.db import init_db, SessionLocal
from app.models import User, JobRow
from app.quota import can_start_job


def test_code_roundtrip():
    c = generate_code(6)
    assert len(c) == 6 and c.isdigit()
    h = hash_code(c, "pepper")
    assert verify_code(c, h, "pepper")
    assert not verify_code("000000", h, "pepper")


def test_api_key_format():
    k = new_api_key()
    assert k.startswith("vw_")
    assert hash_api_key(k) != k


def test_plan_segments_short():
    spans = plan_segments(100, threshold=900, seg=720, overlap=30)
    assert len(spans) == 1
    assert spans[0] == (0.0, 100.0)


def test_plan_segments_long():
    spans = plan_segments(3600, threshold=900, seg=720, overlap=30)
    assert len(spans) > 1
    assert spans[0][0] == 0.0
    assert spans[-1][1] == 3600.0
    # coverage with overlap: each next start strictly before previous end
    for i in range(1, len(spans)):
        assert spans[i][0] < spans[i - 1][1]


def test_concurrency_limits():
    assert concurrency_limit(None, False) == get_settings().guest_global_concurrency
    assert concurrency_limit("user", True) == get_settings().user_concurrency
    assert concurrency_limit("vip", True) == get_settings().vip_concurrency


def test_can_start_job_guest_cap():
    os.makedirs("jobs_data", exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        db.query(JobRow).filter(JobRow.job_id.like("job_test_guest_%")).delete()
        db.commit()
        ok, reason = can_start_job(db, None, None)
        assert ok and reason == "ok"
        db.add(JobRow(job_id="job_test_guest_1", status="running", user_id=None))
        db.commit()
        ok2, reason2 = can_start_job(db, None, None)
        assert not ok2 and reason2 == "guest_queue"
    finally:
        db.query(JobRow).filter(JobRow.job_id.like("job_test_guest_%")).delete()
        db.commit()
        db.close()
