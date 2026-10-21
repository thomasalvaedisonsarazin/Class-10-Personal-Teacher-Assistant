"""Partner program: codes, sign-in as partner, commissions, renewals, payouts, admin."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.main import app as fastapi_app
from app.models.billing import Purchase
from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, UserRole
from app.models.partner import Commission, Partner
from app.models.user import User
from app.services import billing_service, email_auth_service, partner_service
from app.services.billing_service import account_tag
from app.services.play_billing import get_play_verifier
from tests.test_billing import FakePlay

Headers = Callable[[User], dict[str, str]]


@pytest.fixture()
def play(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakePlay]:
    fake = FakePlay()
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    fastapi_app.dependency_overrides[get_play_verifier] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_play_verifier, None)


@pytest.fixture()
def board(db: Session) -> Board:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(board=board, name="Science", tile_color="#4F8A6B", icon="f", display_order=1)
    chapter = Chapter(subject=subject, title="Motion", display_order=1)
    topic = Topic(chapter=chapter, title="Speed", display_order=1, is_published=True)
    db.add_all([board, subject, chapter, topic])
    db.commit()
    return board


@pytest.fixture()
def admin(make_user: Callable[..., User]) -> User:
    return make_user(role=UserRole.admin)


@pytest.fixture()
def student(make_user: Callable[..., User], board: Board) -> User:
    return make_user(role=UserRole.student, board_id=board.id, medium=Medium.en)


def _create_partner(
    client: TestClient, headers: dict[str, str], email: str = "principal@school.in", **extra: Any
) -> dict[str, Any]:
    res = client.post(
        "/api/v1/admin/partners",
        json={"name": "St Joseph School", "email": email, **extra},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def _partner_login(client: TestClient, db: Session, email: str) -> dict[str, str]:
    code = email_auth_service.create_sign_in_code(db, email)
    res = client.post("/api/v1/auth/email/login", json={"email": email, "code": code})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["role"] == "partner"
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def test_admin_creates_partner_and_partner_signs_in(
    client: TestClient,
    db: Session,
    admin: User,
    student: User,
    auth_headers: Headers,
) -> None:
    created = _create_partner(client, auth_headers(admin))
    assert created["code"].startswith("STJOSE") and created["commissionPct"] == 2.0
    assert created["shareLink"].endswith(f"/r/{created['code']}")
    assert created["signedIn"] is False
    # An existing student's email cannot become a partner.
    taken = client.post(
        "/api/v1/admin/partners",
        json={"name": "Another School", "email": student.email},
        headers=auth_headers(admin),
    )
    assert taken.status_code == 409
    headers = _partner_login(client, db, "principal@school.in")
    me = client.get("/api/v1/partner-program/me", headers=headers).json()
    assert me["code"] == created["code"] and me["studentsJoined"] == 0
    assert me["canRequestPayout"] is False and me["payoutMinimum"] == 500.0
    # Students cannot open the partner dashboard.
    assert (
        client.get("/api/v1/partner-program/me", headers=auth_headers(student)).status_code == 403
    )


def test_student_joins_with_code_once(
    client: TestClient,
    db: Session,
    admin: User,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    first = _create_partner(client, auth_headers(admin))
    second = _create_partner(client, auth_headers(admin), email="teacher@school.in")
    headers = auth_headers(student)
    bad = client.post("/api/v1/referrals", json={"code": "NOPE123"}, headers=headers)
    assert bad.status_code == 404
    typed = first["code"].lower()[:3] + "-" + first["code"].lower()[3:]  # forgiving input
    ok = client.post("/api/v1/referrals", json={"code": typed}, headers=headers)
    assert ok.status_code == 200 and ok.json()["partnerName"] == "St Joseph School"
    again = client.post("/api/v1/referrals", json={"code": first["code"]}, headers=headers)
    assert again.status_code == 200
    other = client.post("/api/v1/referrals", json={"code": second["code"]}, headers=headers)
    assert other.status_code == 409
    # A student who already paid cannot add a code afterwards.
    payer = make_user(role=UserRole.student, board_id=student.board_id, medium=Medium.en)
    db.add(
        Purchase(
            payer_user_id=payer.id,
            beneficiary_user_id=payer.id,
            kind="subscription",
            product_id="premium",
            purchase_token="tok-old-0001",
            expires_at=datetime.now(UTC) + timedelta(days=5),
            last_checked_at=datetime.now(UTC),
        )
    )
    db.commit()
    late = client.post(
        "/api/v1/referrals", json={"code": first["code"]}, headers=auth_headers(payer)
    )
    assert late.status_code == 409


def test_commission_on_purchase_and_every_renewal(
    client: TestClient,
    db: Session,
    play: FakePlay,
    admin: User,
    student: User,
    auth_headers: Headers,
) -> None:
    partner = _create_partner(client, auth_headers(admin))
    headers = auth_headers(student)
    client.post("/api/v1/referrals", json={"code": partner["code"]}, headers=headers)
    play.sub("tok-ref-0001", student, student)
    play.subscriptions["tok-ref-0001"] = dataclasses.replace(
        play.subscriptions["tok-ref-0001"], base_plan_id="monthly", order_id="GPA.1"
    )
    res = client.post(
        "/api/v1/billing/purchases",
        json={"productId": "premium", "purchaseToken": "tok-ref-0001"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    rows = db.scalars(select(Commission)).all()
    # ₹99 → ₹84.15 after Google's 15% → 2% = ₹1.68 (168 paise)
    assert len(rows) == 1 and rows[0].net_paise == 8415 and rows[0].amount_paise == 168
    # Renewal: Google reports a new order; the partner earns again.
    purchase = db.scalar(select(Purchase).where(Purchase.purchase_token == "tok-ref-0001"))
    assert purchase is not None
    purchase.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    purchase.last_checked_at = datetime.now(UTC) - timedelta(hours=2)
    db.commit()
    play.subscriptions["tok-ref-0001"] = dataclasses.replace(
        play.subscriptions["tok-ref-0001"],
        order_id="GPA.1..0",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert billing_service.refresh_due_subscriptions(db, play) == 1
    assert len(db.scalars(select(Commission)).all()) == 2
    # Checking again does not double-count the same order.
    billing_service.refresh_due_subscriptions(db, play)
    assert len(db.scalars(select(Commission)).all()) == 2
    partner_headers = _partner_login(client, db, "principal@school.in")
    me = client.get("/api/v1/partner-program/me", headers=partner_headers).json()
    assert me["studentsJoined"] == 1 and me["payingStudents"] == 1
    assert me["earned"] == 3.36 and me["onHold"] == 3.36 and me["available"] == 0


def _add_commissions(db: Session, partner_id: int, *amounts: int) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    for i, amount in enumerate(amounts):
        db.add(
            Commission(
                partner_id=partner_id,
                purchase_id=None,
                order_key=f"seed-{i}",
                product="monthly",
                net_paise=amount * 50,
                rate_pct=2,
                amount_paise=amount,
                available_at=past,
            )
        )
    db.commit()


def test_payout_request_and_admin_flow(
    client: TestClient,
    db: Session,
    admin: User,
    auth_headers: Headers,
) -> None:
    created = _create_partner(client, auth_headers(admin))
    headers = _partner_login(client, db, "principal@school.in")
    _add_commissions(db, created["id"], 30000)
    low = client.post("/api/v1/partner-program/payouts", headers=headers)
    assert low.status_code == 400  # no payout details yet
    bad_upi = client.put(
        "/api/v1/partner-program/payout-details",
        json={"method": "upi", "upiId": "not a upi"},
        headers=headers,
    )
    assert bad_upi.status_code == 422
    saved = client.put(
        "/api/v1/partner-program/payout-details",
        json={"method": "upi", "upiId": "principal@okhdfc", "pan": "abcde1234f"},
        headers=headers,
    )
    assert saved.status_code == 200 and saved.json()["payoutMethod"] == "UPI ••••@okhdfc"
    partner = db.get(Partner, created["id"])
    assert partner is not None and "okhdfc" not in (partner.payout_details_enc or "")
    below = client.post("/api/v1/partner-program/payouts", headers=headers)
    assert below.status_code == 400 and below.json()["error"]["code"] == "below_minimum"
    _add_commissions(db, created["id"], 25000)
    assert partner_service.ready_partners(db)[0][1] == 55000
    me = client.get("/api/v1/partner-program/me", headers=headers).json()
    assert me["available"] == 550.0 and me["canRequestPayout"] is True
    req = client.post("/api/v1/partner-program/payouts", headers=headers)
    assert req.status_code == 201 and req.json()["amount"] == 550.0
    assert client.post("/api/v1/partner-program/payouts", headers=headers).status_code == 409

    admin_headers = auth_headers(admin)
    payouts = client.get("/api/v1/admin/payouts?status=requested", headers=admin_headers).json()
    assert payouts[0]["payoutDetails"] == {"method": "upi", "upi": "principal@okhdfc"}
    assert payouts[0]["pan"] == "ABCDE1234F"
    pid = payouts[0]["id"]
    assert (
        client.post(f"/api/v1/admin/payouts/{pid}/approve", json={}, headers=admin_headers).json()[
            "status"
        ]
        == "approved"
    )
    no_ref = client.post(f"/api/v1/admin/payouts/{pid}/paid", json={}, headers=admin_headers)
    assert no_ref.status_code == 400
    paid = client.post(
        f"/api/v1/admin/payouts/{pid}/paid", json={"reference": "UPI123456"}, headers=admin_headers
    )
    assert paid.json()["status"] == "paid"
    me = client.get("/api/v1/partner-program/me", headers=headers).json()
    assert me["paid"] == 550.0 and me["available"] == 0 and me["payouts"][0]["status"] == "paid"


def test_rejected_payout_returns_money_to_available(
    client: TestClient, db: Session, admin: User, auth_headers: Headers
) -> None:
    created = _create_partner(client, auth_headers(admin))
    headers = _partner_login(client, db, "principal@school.in")
    _add_commissions(db, created["id"], 60000)
    client.put(
        "/api/v1/partner-program/payout-details",
        json={
            "method": "bank",
            "holderName": "A Principal",
            "accountNumber": "123456789012",
            "ifsc": "sbin0001234",
        },
        headers=headers,
    )
    pid = client.post("/api/v1/partner-program/payouts", headers=headers).json()["id"]
    res = client.post(
        f"/api/v1/admin/payouts/{pid}/reject",
        json={"note": "wrong IFSC"},
        headers=auth_headers(admin),
    )
    assert res.json()["status"] == "rejected"
    me = client.get("/api/v1/partner-program/me", headers=headers).json()
    assert me["available"] == 600.0 and me["payoutMethod"] == "Bank ••••9012"


def test_admin_changes_rate_and_partner_endpoints_need_admin(
    client: TestClient, db: Session, admin: User, student: User, auth_headers: Headers
) -> None:
    created = _create_partner(client, auth_headers(admin), commissionPct=5)
    assert created["commissionPct"] == 5.0
    res = client.patch(
        f"/api/v1/admin/partners/{created['id']}",
        json={"commissionPct": 3.5, "isActive": False},
        headers=auth_headers(admin),
    )
    assert res.json()["commissionPct"] == 3.5 and res.json()["isActive"] is False
    assert client.get("/api/v1/admin/partners", headers=auth_headers(student)).status_code == 403
    # Inactive partner codes no longer work.
    gone = client.post(
        "/api/v1/referrals", json={"code": created["code"]}, headers=auth_headers(student)
    )
    assert gone.status_code == 404


def test_share_link_opens_play_store_with_code(client: TestClient) -> None:
    res = client.get("/r/stjo-se7k2", follow_redirects=False)
    assert res.status_code == 302
    location = res.headers["location"]
    assert "id=com.edsolution.teacherassistant" in location
    assert "referrer=pta_ref%3DSTJOSE7K2" in location


def test_account_tag_unchanged() -> None:
    assert account_tag(7) == "pta-7"
