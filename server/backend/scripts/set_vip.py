#!/usr/bin/env python3
"""Set user tier: python scripts/set_vip.py --email a@b.com --tier vip"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal, init_db
from app.models import User


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--tier", choices=["user", "vip"], default="vip")
    args = p.parse_args()
    init_db()
    db = SessionLocal()
    email = args.email.lower().strip()
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(email=email, tier=args.tier, is_active=True)
        db.add(u)
        print(f"created user {email} tier={args.tier}")
    else:
        u.tier = args.tier
        print(f"updated {email} tier={args.tier}")
    db.commit()
    db.close()


if __name__ == "__main__":
    main()
