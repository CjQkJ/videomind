import os
import sys

import pytest
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from app import auth_routes
from app.config import DEFAULT_SECRET_KEY, Settings, validate_runtime_security
from app.db import Base


def test_production_rejects_default_jwt_secret():
    settings = Settings(environment="production", secret_key=DEFAULT_SECRET_KEY)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_runtime_security(settings)


def test_production_rejects_missing_smtp_credentials():
    settings = Settings(
        environment="production",
        secret_key="a-production-secret-that-is-not-the-default",
        smtp_user="",
        smtp_password="",
    )

    with pytest.raises(RuntimeError, match="SMTP"):
        validate_runtime_security(settings)


def test_production_rejects_wildcard_cors():
    settings = Settings(
        environment="production",
        secret_key="a-production-secret-that-is-not-the-default",
        smtp_user="mailer@example.com",
        smtp_password="smtp-secret",
        cors_origins="https://example.com,*",
    )

    with pytest.raises(RuntimeError, match="CORS"):
        validate_runtime_security(settings)


def test_default_app_has_no_permissive_credentialed_cors():
    cors = [item for item in main.app.user_middleware if item.cls is CORSMiddleware]

    assert not cors or "*" not in cors[0].kwargs.get("allow_origins", [])


def test_production_never_returns_dev_verification_code(monkeypatch):
    settings = Settings(
        environment="production",
        secret_key="a-production-secret-that-is-not-the-default",
        smtp_user="",
        smtp_password="",
        allow_dev_codes=True,
    )
    monkeypatch.setattr(auth_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth_routes,
        "send_verification_email",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("smtp missing")),
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        with pytest.raises(HTTPException) as exc_info:
            auth_routes._send_code(db, "user@example.com", "register")
    finally:
        db.close()
        engine.dispose()

    assert exc_info.value.status_code == 503
