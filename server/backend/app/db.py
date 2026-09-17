import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # lightweight SQLite column migrations
    s = get_settings()
    db_url = s.database_url
    if db_url.startswith("sqlite"):
        m = re.search(r"sqlite:///(.+)", db_url)
        if m:
            _ensure_columns(m.group(1), {
                "users": {"password_hash": "TEXT", "role": "TEXT DEFAULT 'user'"},
                "email_codes": {"purpose": "TEXT DEFAULT 'login'"},
            })
            _seed_admin_role()


def _ensure_columns(db_path: str, table_cols: dict):
    if not os.path.exists(db_path):
        return
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for table, cols in table_cols.items():
        existing = {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        for col_name, col_type in cols.items():
            if col_name not in existing:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
    conn.commit()
    conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def _seed_admin_role() -> None:
    """Promote configured admin_email to role=admin if it exists."""
    from app.config import get_settings
    from app.models import User

    admin_email = get_settings().admin_email.lower().strip()
    if not admin_email:
        return
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.email == admin_email).first()
        if row and getattr(row, "role", None) != "admin":
            row.role = "admin"
            db.commit()
    finally:
        db.close()
