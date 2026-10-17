"""Who may open paid topics, and recording verified Google Play purchases.

Access rules (only when ``BILLING_ENABLED``; otherwise everything is free):
- The first ``FREE_TOPICS_PER_SUBJECT`` topics of every subject are free.
- An active subscription opens every topic for its student (a parent pays one
  subscription product per child: ``premium``, ``premium_2``, ``premium_3``).
- A bought single topic stays open forever and skips the study order
  (see :mod:`app.services.progress_service`).

Purchases are never trusted from the app: each purchase token is checked with Google,
bound to the payer's account, used only once, then acknowledged or consumed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppError, BadRequestError, ConflictError, ForbiddenError
from app.models.billing import Purchase
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.billing import BillingStatusOut, PurchaseIn, PurchaseOut
from app.services.play_billing import PlayVerifier, get_play_verifier

logger = logging.getLogger(__name__)

RECHECK_AFTER = timedelta(hours=1)  # how often an expired auto-renewing plan is re-checked


class TopicAccess(StrEnum):
    """Why a student may (or may not) open a topic's lessons and test."""

    free = "free"
    premium = "premium"  # active subscription
    purchased = "purchased"  # this topic was bought
    payment_required = "payment_required"


class PaymentRequiredError(AppError):
    """402: the topic needs a plan or a single-topic purchase."""

    status_code = 402
    code = "payment_required"
    message = "Unlock this topic with a plan, or buy just this topic"


@dataclass(frozen=True)
class StudentAccess:
    """A student's paid access at one moment."""

    premium_until: datetime | None = None
    topic_ids: frozenset[int] = field(default_factory=frozenset)

    def access(self, topic_id: int, position: int) -> TopicAccess:
        """Access for a topic at ``position`` (0-based) in its subject's study order."""
        if not settings.BILLING_ENABLED or position < settings.FREE_TOPICS_PER_SUBJECT:
            return TopicAccess.free
        if self.premium_until is not None:
            return TopicAccess.premium
        if topic_id in self.topic_ids:
            return TopicAccess.purchased
        return TopicAccess.payment_required


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _refresh_subscription(db: Session, row: Purchase, verifier: PlayVerifier | None) -> None:
    """Re-check an expired auto-renewing subscription with Google (at most hourly)."""
    if verifier is None or _aware(row.last_checked_at) > _now() - RECHECK_AFTER:
        return
    try:
        info = verifier.get_subscription(row.purchase_token)
    except AppError:
        return  # keep the stored state; try again later
    row.last_checked_at = _now()
    if info.expires_at is not None:
        row.expires_at = info.expires_at
    row.auto_renewing = info.auto_renewing and info.active
    db.commit()


def _optional_verifier() -> PlayVerifier | None:
    """The Play client when configured (used only to pick up renewals)."""
    if not settings.PLAY_SERVICE_ACCOUNT_JSON:
        return None
    try:
        return get_play_verifier()
    except Exception:  # a broken service account must never block studying
        logger.exception("Google Play client could not be created")
        return None


def get_student_access(
    db: Session, student: User, verifier: PlayVerifier | None = None
) -> StudentAccess:
    """Current paid access of ``student`` (renewals are picked up lazily via ``verifier``)."""
    if not settings.BILLING_ENABLED:
        return StudentAccess()
    now = _now()
    rows = db.scalars(select(Purchase).where(Purchase.beneficiary_user_id == student.id)).all()
    premium_until: datetime | None = None
    topic_ids: set[int] = set()
    for row in rows:
        if row.kind == "topic" and row.topic_id is not None:
            topic_ids.add(row.topic_id)
            continue
        if row.expires_at is None:
            continue
        if row.kind == "subscription" and row.auto_renewing and _aware(row.expires_at) <= now:
            _refresh_subscription(db, row, verifier or _optional_verifier())
        expires = _aware(row.expires_at)
        if expires > now and (premium_until is None or expires > premium_until):
            premium_until = expires
    return StudentAccess(premium_until=premium_until, topic_ids=frozenset(topic_ids))


def _beneficiary(db: Session, payer: User, student_id: int | None) -> User:
    if payer.role == UserRole.parent:
        from app.services import parent_service  # avoids an import cycle via progress_service

        if student_id is None:
            raise BadRequestError("Choose which child this is for", code="child_required")
        return parent_service.linked_student(db, payer, student_id)
    if payer.role == UserRole.student and student_id in (None, payer.id):
        return payer
    raise ForbiddenError("Only students and parents can buy plans")


PROFILE_TAG = re.compile(r"pta-(\d+)(?:-t(\d+))?")


def account_tag(user_id: int) -> str:
    """Opaque id the app passes to Google Play (obfuscatedAccountId / ProfileId)."""
    return f"pta-{user_id}"


def topic_profile_tag(student_id: int, topic_id: int) -> str:
    """ProfileId for a single-topic purchase: Google keeps the topic with the payment."""
    return f"{account_tag(student_id)}-t{topic_id}"


def _check_owner(
    account_id: str | None, profile_id: str | None, payer: User, student: User
) -> int | None:
    """Check the purchase belongs to this payer and student; return the topic in it, if any."""
    if account_id is not None and account_id != account_tag(payer.id):
        raise ForbiddenError("This purchase belongs to another account", code="purchase_mismatch")
    if profile_id is None:
        return None
    match = PROFILE_TAG.fullmatch(profile_id)
    if match is None or int(match.group(1)) != student.id:
        raise ForbiddenError("This purchase was made for another student", code="purchase_mismatch")
    return int(match.group(2)) if match.group(2) else None


def _existing(db: Session, token: str, payer: User) -> Purchase | None:
    row = db.scalar(select(Purchase).where(Purchase.purchase_token == token))
    if row is not None and row.payer_user_id != payer.id:
        raise ConflictError("This purchase was already used", code="purchase_used")
    return row


def record_purchase(
    db: Session, payer: User, data: PurchaseIn, verifier: PlayVerifier
) -> PurchaseOut:
    """Verify a Google Play purchase and give its student access (idempotent per token).

    Raises:
        BadRequestError: unknown product, missing topic/child, or Google says not paid
        ForbiddenError: the purchase belongs to another account or student
        ConflictError: the token was already claimed by someone else
    """
    student = _beneficiary(db, payer, data.student_id)
    existing = _existing(db, data.purchase_token, payer)
    if existing is not None:
        return PurchaseOut.from_row(existing)
    now = _now()
    product_id = data.product_id

    if product_id in settings.PLAY_SUBSCRIPTION_IDS:
        sub = verifier.get_subscription(data.purchase_token)
        if sub.product_id != product_id or not sub.active:
            raise BadRequestError("Google Play has no active plan for this", code="not_paid")
        _check_owner(sub.account_id, sub.profile_id, payer, student)
        row = Purchase(
            kind="subscription",
            expires_at=sub.expires_at,
            auto_renewing=sub.auto_renewing,
            order_id=sub.order_id,
        )
        acknowledge = not sub.acknowledged
    elif product_id == settings.PLAY_TOPIC_PRODUCT_ID:
        from app.services.progress_service import get_topic_for_student

        product = verifier.get_product(product_id, data.purchase_token)
        if not product.purchased:
            raise BadRequestError("Google Play has no payment for this purchase", code="not_paid")
        paid_topic = _check_owner(product.account_id, product.profile_id, payer, student)
        if data.topic_id is not None and paid_topic not in (None, data.topic_id):
            raise ForbiddenError("This payment was for another topic", code="purchase_mismatch")
        topic_id = paid_topic if paid_topic is not None else data.topic_id
        if topic_id is None:
            raise BadRequestError("Choose the topic to unlock", code="topic_required")
        row = Purchase(
            kind="topic",
            topic_id=get_topic_for_student(db, student, topic_id).id,
            order_id=product.order_id,
        )
        acknowledge = not product.consumed
    else:
        raise BadRequestError("Unknown product", code="unknown_product")

    row.payer_user_id = payer.id
    row.beneficiary_user_id = student.id
    row.product_id = product_id
    row.purchase_token = data.purchase_token
    row.last_checked_at = now
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:  # the same token raced in twice
        db.rollback()
        raise ConflictError("This purchase was already used", code="purchase_used") from exc
    if acknowledge:
        _finish_with_google(verifier, row)
    logger.info("Purchase recorded kind=%s student_id=%s", row.kind, student.id)
    return PurchaseOut.from_row(row)


def _finish_with_google(verifier: PlayVerifier, row: Purchase) -> None:
    """Acknowledge / consume after access is saved (Google refunds unacknowledged buys)."""
    try:
        if row.kind == "subscription":
            verifier.acknowledge_subscription(row.product_id, row.purchase_token)
        else:
            verifier.consume_product(row.product_id, row.purchase_token)
    except AppError:
        logger.warning("Could not acknowledge purchase %s; the app will retry", row.id)


def billing_status(db: Session, user: User, student_id: int | None) -> BillingStatusOut:
    """Plan status for the signed-in student, or a parent's linked child."""
    student = _beneficiary(db, user, student_id)
    access = get_student_access(db, student)
    return BillingStatusOut(
        billing_enabled=settings.BILLING_ENABLED,
        student_id=student.id,
        premium_until=access.premium_until,
        purchased_topic_ids=sorted(access.topic_ids),
        free_topics_per_subject=settings.FREE_TOPICS_PER_SUBJECT,
        next_subscription_id=next_subscription_id(db, user),
        account_tag=account_tag(user.id),
        profile_tag=account_tag(student.id),
    )


def next_subscription_id(db: Session, payer: User) -> str | None:
    """The plan product this payer can still subscribe to (None when all are in use).

    A product stays in use while it renews or until its paid period ends.
    """
    now = _now()
    rows = db.execute(
        select(Purchase.product_id, Purchase.expires_at, Purchase.auto_renewing).where(
            Purchase.payer_user_id == payer.id, Purchase.kind == "subscription"
        )
    ).all()
    in_use = {
        product_id
        for product_id, expires_at, renewing in rows
        if renewing or (expires_at is not None and _aware(expires_at) > now)
    }
    return next((pid for pid in settings.PLAY_SUBSCRIPTION_IDS if pid not in in_use), None)
