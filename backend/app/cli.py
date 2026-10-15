"""Management CLI.

Usage::

    python -m app.cli create-admin --email admin@example.com [--name "Admin"]
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.enums import UserRole
from app.models.user import User

logger = logging.getLogger("app.cli")


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


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Create or promote an admin user")
    admin.add_argument("--email", required=True, help="Google account email of the admin")
    admin.add_argument("--name", default=None, help="Full name")

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        try:
            create_admin(args.email, args.name)
        except ValueError as exc:
            logger.error("%s", exc)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
