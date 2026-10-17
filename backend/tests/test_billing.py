"""Payments: free first topic, paywall (402), Google Play purchases, parents paying, renewals."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.main import app as fastapi_app
from app.models.billing import Purchase
from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, ParentLinkStatus, UserRole
from app.models.parent import ParentLink
from app.models.user import User
from app.services.billing_service import account_tag, topic_profile_tag
from app.services.play_billing import PlayProduct, PlaySubscription, get_play_verifier

Headers = Callable[[User], dict[str, str]]
FUTURE = datetime.now(UTC) + timedelta(days=30)


@dataclass
class FakePlay:
    """In-memory Google Play: tokens -> what Google would answer."""

    subscriptions: dict[str, PlaySubscription] = field(default_factory=dict)
    products: dict[str, PlayProduct] = field(default_factory=dict)
    acknowledged: list[str] = field(default_factory=list)
    consumed: list[str] = field(default_factory=list)

    def get_subscription(self, token: str) -> PlaySubscription:
        return self.subscriptions.get(
            token, PlaySubscription("", "INVALID", None, False, False, None, None, None)
        )

    def acknowledge_subscription(self, product_id: str, token: str) -> None:
        self.acknowledged.append(token)

    def get_product(self, product_id: str, token: str) -> PlayProduct:
        return self.products.get(token, PlayProduct(False, False, None, None, None))

    def consume_product(self, product_id: str, token: str) -> None:
        self.consumed.append(token)

    def sub(self, token: str, payer: User, student: User, expires: datetime = FUTURE) -> None:
        self.subscriptions[token] = PlaySubscription(
            product_id="premium",
            state="SUBSCRIPTION_STATE_ACTIVE",
            expires_at=expires,
            auto_renewing=True,
            acknowledged=False,
            account_id=account_tag(payer.id),
            profile_id=account_tag(student.id),
            order_id="GPA.1",
        )

    def product(self, token: str, payer: User, student: User) -> None:
        self.products[token] = PlayProduct(
            True, False, account_tag(payer.id), account_tag(student.id), "GPA.2"
        )


@pytest.fixture()
def play(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakePlay]:
    fake = FakePlay()
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    fastapi_app.dependency_overrides[get_play_verifier] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_play_verifier, None)


@pytest.fixture()
def topics(db: Session) -> list[Topic]:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(board=board, name="Science", tile_color="#4F8A6B", icon="f", display_order=1)
    chapter = Chapter(subject=subject, title="Motion", display_order=1)
    items = [
        Topic(chapter=chapter, title=f"T{i}", display_order=i, is_published=True)
        for i in range(1, 5)
    ]
    db.add_all([board, subject, chapter, *items])
    db.commit()
    return items


@pytest.fixture()
def student(make_user: Callable[..., User], topics: list[Topic]) -> User:
    board_id = topics[0].chapter.subject.board_id
    return make_user(role=UserRole.student, board_id=board_id, medium=Medium.en)


def _start(client: TestClient, headers: dict[str, str], topic: Topic) -> int:
    return client.post(f"/api/v1/topics/{topic.id}/start", headers=headers).status_code


def _buy(client: TestClient, headers: dict[str, str], **body: object) -> Any:
    return client.post("/api/v1/billing/purchases", json=body, headers=headers)


def _subject_access(client: TestClient, headers: dict[str, str], topics: list[Topic]) -> list[str]:
    subject_id = topics[0].chapter.subject_id
    data = client.get(f"/api/v1/subjects/{subject_id}", headers=headers).json()
    return [t["access"] for ch in data["chapters"] for t in ch["topics"]]


def test_billing_off_keeps_everything_free(
    client: TestClient, student: User, topics: list[Topic], auth_headers: Headers
) -> None:
    assert _subject_access(client, auth_headers(student), topics) == ["free"] * 4


def test_first_topic_free_then_payment_required(
    client: TestClient,
    db: Session,
    play: FakePlay,
    student: User,
    topics: list[Topic],
    auth_headers: Headers,
) -> None:
    headers = auth_headers(student)
    assert _subject_access(client, headers, topics)[:2] == ["free", "payment_required"]
    assert _start(client, headers, topics[0]) == 200
    # Pass topic 1 so topic 2 is unlocked by order but still needs payment.
    from app.services.progress_service import record_quiz_result

    record_quiz_result(db, student, topics[0], 80)
    db.commit()
    res = client.post(f"/api/v1/topics/{topics[1].id}/start", headers=headers)
    assert res.status_code == 402 and res.json()["error"]["code"] == "payment_required"
    # The topic screen still opens, to offer unlocking.
    detail = client.get(f"/api/v1/topics/{topics[1].id}", headers=headers)
    assert detail.status_code == 200 and detail.json()["access"] == "payment_required"


def test_subscription_unlocks_everything_and_is_single_use(
    client: TestClient,
    db: Session,
    play: FakePlay,
    student: User,
    topics: list[Topic],
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    headers = auth_headers(student)
    play.sub("tok-sub-0001", student, student)
    res = _buy(client, headers, productId="premium", purchaseToken="tok-sub-0001")
    assert res.status_code == 200, res.text
    assert res.json()["kind"] == "subscription"
    assert play.acknowledged == ["tok-sub-0001"]
    assert _subject_access(client, headers, topics) == ["free"] + ["premium"] * 3
    # Same token again: idempotent for the payer, refused for anyone else.
    again_mine = _buy(client, headers, productId="premium", purchaseToken="tok-sub-0001")
    assert again_mine.status_code == 200
    other = make_user(role=UserRole.student, board_id=student.board_id, medium=Medium.en)
    again = _buy(client, auth_headers(other), productId="premium", purchaseToken="tok-sub-0001")
    assert again.status_code == 409
    assert db.scalar(select(Purchase.id).where(Purchase.beneficiary_user_id == other.id)) is None


def test_purchase_from_another_account_is_refused(
    client: TestClient,
    play: FakePlay,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    someone = make_user(role=UserRole.student)
    play.sub("tok-sub-xxxx", someone, someone)
    res = _buy(client, auth_headers(student), productId="premium", purchaseToken="tok-sub-xxxx")
    assert res.status_code == 403


def test_unpaid_or_unknown_purchase_is_refused(
    client: TestClient, play: FakePlay, student: User, auth_headers: Headers
) -> None:
    headers = auth_headers(student)
    assert _buy(client, headers, productId="premium", purchaseToken="tok-none-1").status_code == 400
    bad = _buy(client, headers, productId="gold", purchaseToken="tok-none-2")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_product"


def test_bought_topic_opens_directly_and_is_consumed(
    client: TestClient, play: FakePlay, student: User, topics: list[Topic], auth_headers: Headers
) -> None:
    headers = auth_headers(student)
    last = topics[3]
    assert _start(client, headers, last) == 403  # locked by order, not passed earlier topics
    play.product("tok-topic-1", student, student)
    res = _buy(
        client, headers, productId="topic_unlock", purchaseToken="tok-topic-1", topicId=last.id
    )
    assert res.status_code == 200, res.text
    assert res.json()["topicId"] == last.id and res.json()["expiresAt"] is None
    assert play.consumed == ["tok-topic-1"]
    assert _start(client, headers, last) == 200
    assert _subject_access(client, headers, topics) == [
        "free",
        "payment_required",
        "payment_required",
        "purchased",
    ]
    no_topic = _buy(client, headers, productId="topic_unlock", purchaseToken="tok-topic-2")
    assert no_topic.status_code == 400



def test_topic_comes_from_the_google_purchase(
    client: TestClient, play: FakePlay, student: User, topics: list[Topic], auth_headers: Headers
) -> None:
    """A delayed (UPI pending) purchase is finished later without the app remembering it."""
    headers = auth_headers(student)
    play.products["tok-topic-9"] = PlayProduct(
        True, False, account_tag(student.id), topic_profile_tag(student.id, topics[2].id), "GPA.3"
    )
    wrong = _buy(
        client, headers, productId="topic_unlock", purchaseToken="tok-topic-9", topicId=topics[3].id
    )
    assert wrong.status_code == 403
    res = _buy(client, headers, productId="topic_unlock", purchaseToken="tok-topic-9")
    assert res.status_code == 200 and res.json()["topicId"] == topics[2].id


def _link(db: Session, parent: User, child: User, code: str) -> None:
    db.add(
        ParentLink(
            parent_user_id=parent.id,
            student_user_id=child.id,
            invite_code=code,
            invite_expires_at=FUTURE,
            status=ParentLinkStatus.accepted,
        )
    )
    db.commit()


def test_parent_pays_a_renewing_plan_per_child(
    client: TestClient,
    db: Session,
    play: FakePlay,
    student: User,
    topics: list[Topic],
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    parent = make_user(role=UserRole.parent, medium=Medium.en)
    sibling = make_user(role=UserRole.student, board_id=student.board_id, medium=Medium.en)
    stranger = make_user(role=UserRole.student, board_id=student.board_id)
    _link(db, parent, student, "ABCDEFGH")
    _link(db, parent, sibling, "BCDEFGHJ")
    headers = auth_headers(parent)

    def status(child: User) -> dict[str, Any]:
        url = f"/api/v1/billing/status?studentId={child.id}"
        data: dict[str, Any] = client.get(url, headers=headers).json()
        return data

    assert status(student)["nextSubscriptionId"] == "premium"
    play.sub("tok-parent-1", parent, student)
    missing_child = _buy(client, headers, productId="premium", purchaseToken="tok-parent-1")
    assert missing_child.status_code == 400
    play.sub("tok-parent-x", parent, stranger)
    not_mine = _buy(
        client, headers, productId="premium", purchaseToken="tok-parent-x", studentId=stranger.id
    )
    assert not_mine.status_code == 404
    first = _buy(
        client, headers, productId="premium", purchaseToken="tok-parent-1", studentId=student.id
    )
    assert first.status_code == 200, first.text

    # The second child gets the next plan product, also auto-renewing.
    after_first = status(sibling)
    assert after_first["nextSubscriptionId"] == "premium_2"
    assert after_first["profileTag"] == account_tag(sibling.id)
    play.sub("tok-parent-2", parent, sibling)
    play.subscriptions["tok-parent-2"] = PlaySubscription(
        **{**play.subscriptions["tok-parent-2"].__dict__, "product_id": "premium_2"}
    )
    second = _buy(
        client, headers, productId="premium_2", purchaseToken="tok-parent-2", studentId=sibling.id
    )
    assert second.status_code == 200, second.text
    assert status(sibling)["premiumUntil"] is not None
    assert status(sibling)["nextSubscriptionId"] == "premium_3"
    assert _subject_access(client, auth_headers(student), topics)[1] == "premium"
    assert _subject_access(client, auth_headers(sibling), topics)[1] == "premium"


def test_expired_subscription_picks_up_renewal(
    client: TestClient,
    db: Session,
    play: FakePlay,
    student: User,
    topics: list[Topic],
    auth_headers: Headers,
) -> None:
    headers = auth_headers(student)
    play.sub("tok-renew-1", student, student)
    bought = _buy(client, headers, productId="premium", purchaseToken="tok-renew-1")
    assert bought.status_code == 200
    row = db.scalar(select(Purchase).where(Purchase.purchase_token == "tok-renew-1"))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    row.last_checked_at = datetime.now(UTC) - timedelta(hours=2)
    db.commit()
    # Google says it renewed: the next look-up extends access.
    from app.services import billing_service

    access = billing_service.get_student_access(db, student, play)
    assert access.premium_until is not None and access.premium_until > datetime.now(UTC)


def test_production_billing_needs_service_account() -> None:
    with pytest.raises(ValueError, match="PLAY_SERVICE_ACCOUNT_JSON"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="k" * 40,
            DEV_LOGIN_ENABLED=False,
            EMAIL_PROVIDER="smtp",
            SMTP_HOST="smtp.example.com",
            BILLING_ENABLED=True,
        )
