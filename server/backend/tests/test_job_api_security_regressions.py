import json
import os
import sys
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from app.db import Base, get_db
from app.deps import AuthContext, get_auth_context
from app.models import JobRow, User
from app.schemas import CreateJobRequest, RerenderRequest


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


@pytest.fixture()
def jobs_dir(tmp_path, monkeypatch):
    path = tmp_path / "jobs"
    path.mkdir()
    monkeypatch.setattr(main, "JOBS_DIR", str(path))
    return path


@pytest.fixture()
def uploads_dir(tmp_path, monkeypatch):
    path = tmp_path / "uploads"
    path.mkdir()
    monkeypatch.setattr(main, "UPLOADS_DIR", str(path))
    return path


def _add_user(db, email):
    user = User(email=email, tier="user", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_finished_job(db, jobs_dir, owner):
    row = JobRow(
        job_id="job_owned_security_test",
        user_id=owner.id,
        status="succeeded",
        mode="study_note",
    )
    db.add(row)
    db.commit()

    job_dir = jobs_dir / row.job_id
    job_dir.mkdir()
    (job_dir / "result.json").write_text(
        json.dumps({"source": {"title": "owner result"}}),
        encoding="utf-8",
    )
    (job_dir / "result.md").write_text("owner markdown", encoding="utf-8")
    (job_dir / "result.html").write_text("owner html", encoding="utf-8")
    return row, job_dir


def _submit_upload_job(db, jobs_dir, uploads_dir, options):
    file_id = "owned_input.mp4"
    (uploads_dir / file_id).write_bytes(b"0" * 2048)
    payload = {
        "input": {"type": "upload", "file_id": file_id},
        "output": {"mode": "study_note"},
        "options": options,
    }
    try:
        request = CreateJobRequest.model_validate(payload)
        response = main.create_job(
            request,
            AuthContext(user=None, via="guest"),
            db,
        )
    except (HTTPException, ValidationError) as exc:
        return None, exc
    return response, None


@pytest.mark.parametrize("caller_kind", ["other_user", "guest"])
def test_rerender_rejects_non_owner_before_writing(db, jobs_dir, caller_kind):
    owner = _add_user(db, "owner-rerender@example.com")
    row, job_dir = _add_finished_job(db, jobs_dir, owner)
    if caller_kind == "other_user":
        caller = _add_user(db, "intruder-rerender@example.com")
        auth = AuthContext(user=caller, via="jwt")
    else:
        auth = AuthContext(user=None, via="guest")

    before_md = (job_dir / "result.md").read_bytes()
    before_mode = row.mode

    with pytest.raises(HTTPException) as exc_info:
        main.rerender_job(
            row.job_id,
            RerenderRequest(mode="cards", show_source=True),
            auth,
            db,
        )

    assert exc_info.value.status_code == 403
    db.refresh(row)
    assert (job_dir / "result.md").read_bytes() == before_md
    assert row.mode == before_mode


@pytest.mark.parametrize("endpoint", ["status", "result"])
@pytest.mark.parametrize("caller_kind", ["other_user", "guest"])
def test_owned_job_status_and_result_reject_non_owner(
    db, jobs_dir, endpoint, caller_kind
):
    owner = _add_user(db, f"owner-{endpoint}-{caller_kind}@example.com")
    row, _ = _add_finished_job(db, jobs_dir, owner)
    if caller_kind == "other_user":
        caller = _add_user(db, f"intruder-{endpoint}@example.com")
        auth = AuthContext(user=caller, via="jwt")
    else:
        auth = AuthContext(user=None, via="guest")

    target = main.get_job_status if endpoint == "status" else main.get_job_result
    with pytest.raises(HTTPException) as exc_info:
        target(row.job_id, auth, db)

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("suffix", ["result.json", "result.md", "result.html"])
@pytest.mark.parametrize("caller_kind", ["other_user", "guest"])
def test_owned_job_artifacts_reject_non_owner(
    db, jobs_dir, suffix, caller_kind
):
    owner = _add_user(db, f"owner-{suffix}-{caller_kind}@example.com")
    row, _ = _add_finished_job(db, jobs_dir, owner)
    if caller_kind == "other_user":
        caller = _add_user(db, f"intruder-{suffix}@example.com")
        auth = AuthContext(user=caller, via="jwt")
    else:
        auth = AuthContext(user=None, via="guest")

    def override_db():
        yield db

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_auth_context] = lambda: auth
    try:
        response = TestClient(main.app).get(f"/api/v1/jobs/{row.job_id}/{suffix}")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 403


def test_client_upstream_credentials_are_rejected_or_removed_from_job(
    db, jobs_dir, uploads_dir
):
    client_url = "https://attacker.invalid/v1"
    client_key = "sk-client-controlled-secret"

    response, error = _submit_upload_job(
        db,
        jobs_dir,
        uploads_dir,
        {"api_url": client_url, "api_key": client_key},
    )

    if error is not None:
        if isinstance(error, HTTPException):
            assert error.status_code in (400, 422)
        return

    row = db.query(JobRow).filter(JobRow.job_id == response["job_id"]).one()
    assert client_url not in json.dumps(row.options_json)
    assert client_key not in json.dumps(row.options_json)
    assert client_url not in json.dumps(row.request_json)
    assert client_key not in json.dumps(row.request_json)


def test_client_max_duration_cannot_exceed_server_cap(db, jobs_dir, uploads_dir):
    server_cap = main.get_settings().max_video_duration_sec

    response, error = _submit_upload_job(
        db,
        jobs_dir,
        uploads_dir,
        {"max_duration_sec": server_cap + 1},
    )

    if error is not None:
        if isinstance(error, HTTPException):
            assert error.status_code in (400, 422)
        return

    row = db.query(JobRow).filter(JobRow.job_id == response["job_id"]).one()
    stored_limit = (row.options_json or {}).get("max_duration_sec")
    request_limit = ((row.request_json or {}).get("options") or {}).get(
        "max_duration_sec"
    )
    assert stored_limit is None or stored_limit <= server_cap
    assert request_limit is None or request_limit <= server_cap


@pytest.mark.parametrize(
    "invalid_job_id",
    ["..", r"..\outside_job", r"job_valid\child", "job/../outside_job"],
)
def test_status_rejects_unsafe_job_id(db, jobs_dir, invalid_job_id):
    with pytest.raises(HTTPException) as exc_info:
        main.get_job_status(
            invalid_job_id,
            AuthContext(user=None, via="guest"),
            db,
        )

    assert exc_info.value.status_code == 400


def test_artifact_path_rejects_backslash_traversal(db, jobs_dir):
    outside_dir = jobs_dir.parent / "outside_job"
    outside_dir.mkdir()
    (outside_dir / "result.md").write_text("outside secret", encoding="utf-8")
    unsafe_job_id = r"..\outside_job"

    def override_db():
        yield db

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user=None, via="guest"
    )
    try:
        encoded_id = quote(unsafe_job_id, safe="")
        response = TestClient(main.app).get(
            f"/api/v1/jobs/{encoded_id}/result.md"
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.text != "outside secret"


def test_rerender_rejects_backslash_traversal_before_write(db, jobs_dir):
    outside_dir = jobs_dir.parent / "outside_job"
    outside_dir.mkdir()
    (outside_dir / "result.json").write_text(
        json.dumps({"source": {"title": "outside"}}),
        encoding="utf-8",
    )
    output_path = outside_dir / "result.md"
    output_path.write_text("outside original", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        main.rerender_job(
            r"..\outside_job",
            RerenderRequest(mode="cards", show_source=True),
            AuthContext(user=None, via="guest"),
            db,
        )

    assert exc_info.value.status_code == 400
    assert output_path.read_text(encoding="utf-8") == "outside original"


def test_upload_rejects_stream_over_server_size_limit_and_removes_partial_file(
    db, uploads_dir, monkeypatch
):
    owner = _add_user(db, "upload-size-owner@example.com")
    current = main.get_settings()
    values = current.model_dump() if hasattr(current, "model_dump") else current.dict()
    values.update(max_upload_size_bytes=1024, max_upload_bytes=1024)
    limited_settings = SimpleNamespace(**values)
    monkeypatch.setattr(main, "settings", limited_settings)
    monkeypatch.setattr(main, "get_settings", lambda: limited_settings)

    def override_db():
        yield db

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user=owner, via="jwt"
    )
    try:
        response = TestClient(main.app).post(
            "/api/v1/uploads",
            files={"file": ("too-large.mp4", b"x" * 1025, "video/mp4")},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 413
    assert list(uploads_dir.iterdir()) == []


@pytest.mark.parametrize("caller_kind", ["other_user", "guest"])
def test_uploaded_file_cannot_be_claimed_by_non_owner(
    db, jobs_dir, uploads_dir, caller_kind
):
    owner = _add_user(db, f"upload-owner-{caller_kind}@example.com")
    owner_auth = AuthContext(user=owner, via="jwt")

    def override_db():
        yield db

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_auth_context] = lambda: owner_auth
    client = TestClient(main.app)
    try:
        upload_response = client.post(
            "/api/v1/uploads",
            files={"file": ("owner.mp4", b"x" * 2048, "video/mp4")},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]

        if caller_kind == "other_user":
            caller = _add_user(db, "upload-intruder@example.com")
            caller_auth = AuthContext(user=caller, via="jwt")
        else:
            caller_auth = AuthContext(user=None, via="guest")
        main.app.dependency_overrides[get_auth_context] = lambda: caller_auth

        create_response = client.post(
            "/api/v1/jobs",
            json={
                "input": {"type": "upload", "file_id": file_id},
                "output": {"mode": "study_note"},
            },
        )
    finally:
        main.app.dependency_overrides.clear()

    assert create_response.status_code == 403
    assert db.query(JobRow).filter(JobRow.input_file_id == file_id).count() == 0


def test_uploaded_file_can_be_used_by_its_owner(db, jobs_dir, uploads_dir):
    owner = _add_user(db, "upload-owner-success@example.com")
    owner_auth = AuthContext(user=owner, via="jwt")

    def override_db():
        yield db

    main.app.dependency_overrides[get_db] = override_db
    main.app.dependency_overrides[get_auth_context] = lambda: owner_auth
    client = TestClient(main.app)
    try:
        upload_response = client.post(
            "/api/v1/uploads",
            files={"file": ("owner.mp4", b"x" * 2048, "video/mp4")},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]

        create_response = client.post(
            "/api/v1/jobs",
            json={
                "input": {"type": "upload", "file_id": file_id},
                "output": {"mode": "study_note"},
            },
        )
    finally:
        main.app.dependency_overrides.clear()

    assert create_response.status_code == 200
    row = db.query(JobRow).filter(JobRow.input_file_id == file_id).one()
    assert row.user_id == owner.id


def test_html_artifact_is_served_in_csp_sandbox(db, jobs_dir):
    owner = _add_user(db, "html-sandbox-owner@example.com")
    row, _ = _add_finished_job(db, jobs_dir, owner)
    auth = AuthContext(user=owner, via="jwt")

    response = main.get_result_html(row.job_id, auth, db)

    policy = response.headers.get("content-security-policy", "")
    assert "sandbox" in policy
    assert "default-src 'none'" in policy
    assert response.headers.get("x-content-type-options") == "nosniff"
