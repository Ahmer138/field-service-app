from __future__ import annotations

import argparse
import json
import sys

from app.db import SessionLocal
from app.services import run_retention, storage_service


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply configured retention policies to locations, presence, and photos."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted without mutating the database or object storage.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = run_retention(
            db,
            storage_service=storage_service,
            dry_run=args.dry_run,
        )

    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    return 1 if summary.has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
