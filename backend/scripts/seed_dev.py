"""
Idempotent dev seed script.

Creates a manager and a technician if they do not already exist.
Safe to re-run without duplicating records.

Usage (from backend/):
    python scripts/seed_dev.py

Requires the local Postgres container to be reachable at the DATABASE_URL
configured in .env or the default localhost:5432 fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from backend/ or from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole

DEV_USERS: list[dict] = [
    {
        "email": "manager@fieldservice.dev",
        "password": "Manager@123",
        "role": UserRole.MANAGER,
        "full_name": "Dev Manager",
        "technician_code": None,
        "is_active": True,
    },
    {
        "email": "tech1@fieldservice.dev",
        "password": "Tech@123",
        "role": UserRole.TECHNICIAN,
        "full_name": "Dev Technician",
        "technician_code": "DXB-001",
        "is_active": True,
    },
]


def seed(db: Session) -> None:
    created: list[str] = []
    skipped: list[str] = []

    for spec in DEV_USERS:
        existing = db.query(User).filter(User.email == spec["email"]).first()
        if existing:
            skipped.append(spec["email"])
            continue

        user = User(
            email=spec["email"],
            password_hash=get_password_hash(spec["password"]),
            role=spec["role"],
            full_name=spec["full_name"],
            technician_code=spec["technician_code"],
            is_active=spec["is_active"],
        )
        db.add(user)
        created.append(spec["email"])

    db.commit()

    print("\n=== Dev Seed Result ===")
    for spec in DEV_USERS:
        tag = "CREATED" if spec["email"] in created else "already exists"
        print(f"  [{tag}] {spec['role'].value:12} | {spec['email']} | password: {spec['password']}")
        if spec["technician_code"]:
            print(f"              technician_code: {spec['technician_code']}")
    print()
    print("Working credentials:")
    print("  Manager  -> email: manager@fieldservice.dev  password: Manager@123")
    print("  Tech     -> email: tech1@fieldservice.dev    password: Tech@123")
    print()


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as db:
        seed(db)


if __name__ == "__main__":
    main()
