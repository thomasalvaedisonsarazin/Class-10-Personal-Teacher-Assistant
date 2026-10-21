"""Management CLI.

Usage::

    python -m app.cli create-admin --email admin@example.com [--name "Admin"]
    python -m app.cli import-curriculum [data/curriculum/tn_sslc_full.json]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import func, select

from app.database import SessionLocal
from app.exceptions import AppError
from app.models.enums import UserRole
from app.models.user import User

logger = logging.getLogger("app.cli")

DEFAULT_CURRICULUM = (
    Path(__file__).resolve().parent.parent / "data" / "curriculum" / "tn_sslc_full.json"
)


def create_admin(email: str, name: str | None = None) -> User:
    """Create a user with role=admin, or promote/reactivate an existing one.

    The admin signs in with Google using this email address.
    """
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise ValueError(f"Invalid email: {email!r}")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == normalized))
        if user is None:
            user = User(email=normalized, full_name=name, role=UserRole.admin, is_active=True)
            db.add(user)
            action = "Created"
        else:
            user.role = UserRole.admin
            user.is_active = True
            if name:
                user.full_name = name
            action = "Updated"
        db.commit()
        db.refresh(user)
        logger.info("%s admin user id=%s email=%s", action, user.id, user.email)
        return user


def import_curriculum_file(path: Path) -> dict[str, dict[str, int]]:
    """Load a syllabus JSON file (same format as the admin "Import syllabus") into the database.

    Args:
        path: JSON file with ``boardCode`` and ``subjects``

    Returns:
        Counts of created and updated subjects/chapters/topics
    """
    from app.schemas.admin import CurriculumImport
    from app.services import admin_curriculum_service

    data = CurriculumImport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    with SessionLocal() as db:
        result = admin_curriculum_service.import_curriculum(db, data)
    logger.info("Imported %s: created=%s updated=%s", path.name, result.created, result.updated)
    return {"created": result.created, "updated": result.updated}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Create or promote an admin user")
    admin.add_argument("--email", required=True, help="Google account email of the admin")
    admin.add_argument("--name", default=None, help="Full name")

    curriculum = sub.add_parser(
        "import-curriculum", help="Load a syllabus JSON file (default: full TN SSLC syllabus)"
    )
    curriculum.add_argument("path", nargs="?", type=Path, default=DEFAULT_CURRICULUM)

    sub.add_parser("send-reminders", help="Send today's study reminders (run ~6 pm IST)")
    sub.add_parser("send-parent-weekly", help="Send weekly summaries to parents (Sunday)")
    sub.add_parser("partners-daily", help="Check renewals and send partner payout notices")

    args = parser.parse_args(argv)
    if args.command == "partners-daily":
        from app.services import billing_service, notification_service

        with SessionLocal() as db:
            billing_service.refresh_due_subscriptions(db)
            notification_service.send_partner_payout_ready(db)
        return 0
    if args.command in ("send-reminders", "send-parent-weekly"):
        from app.services import notification_service

        with SessionLocal() as db:
            if args.command == "send-reminders":
                notification_service.send_daily_reminders(db)
            else:
                notification_service.send_parent_weekly(db)
        return 0
    if args.command == "import-curriculum":
        try:
            import_curriculum_file(args.path)
        except (OSError, ValueError, AppError) as exc:
            logger.error("Could not import %s: %s", args.path, exc)
            return 2
        return 0
    if args.command == "create-admin":
        try:
            create_admin(args.email, args.name)
        except ValueError as exc:
            logger.error("%s", exc)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
