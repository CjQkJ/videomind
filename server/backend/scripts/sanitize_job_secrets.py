"""Remove legacy upstream configuration and credentials from persisted jobs."""
from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models import JobRow


SERVER_OWNED_FIELDS = {
    "api_key",
    "api_url",
    "model",
    "max_duration_sec",
    "understand_mode",
}


def sanitize_payload(value):
    if isinstance(value, dict):
        return {
            key: sanitize_payload(item)
            for key, item in value.items()
            if key not in SERVER_OWNED_FIELDS
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return deepcopy(value)


def sanitize_jobs(*, apply: bool) -> tuple[int, int]:
    db = SessionLocal()
    scanned = 0
    changed = 0
    try:
        for row in db.query(JobRow).yield_per(100):
            scanned += 1
            request_json = sanitize_payload(row.request_json)
            options_json = sanitize_payload(row.options_json)
            if request_json != row.request_json or options_json != row.options_json:
                changed += 1
                row.request_json = request_json
                row.options_json = options_json
        if apply:
            db.commit()
        else:
            db.rollback()
        return scanned, changed
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write sanitized JSON back to the configured database",
    )
    args = parser.parse_args()
    scanned, changed = sanitize_jobs(apply=args.apply)
    mode = "applied" if args.apply else "dry-run"
    print(f"[{mode}] scanned={scanned} changed={changed}")


if __name__ == "__main__":
    main()
