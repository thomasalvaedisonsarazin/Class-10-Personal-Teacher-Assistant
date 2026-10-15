"""MVP end-to-end smoke (Validation Gate 2): the whole student journey through the API.

Seeded student: subjects → start topic → lesson → "Not clear" → quiz fail → quiz pass
→ next topic unlocks (and other subjects stay independent).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.seed import seed

CORRECT = "Correct answer"  # offline fake LLM's right option


def _answers(attempt: dict, correct: int) -> list[dict]:
    out = []
    for i, q in enumerate(attempt["questions"]):
        wrong = next(o for o in q["options"] if o != CORRECT)
        out.append({"questionId": q["questionId"], "answer": CORRECT if i < correct else wrong})
    return out


def test_student_journey(client: TestClient, db: Session) -> None:
    seed(db, include_dev_users=True)

    # Sign in (dev) and finish onboarding.
    tokens = client.post("/api/v1/auth/dev-login", json={"email": "student@dev.local"}).json()
    headers = {"Authorization": f"Bearer {tokens['accessToken']}"}
    boards = client.get("/api/v1/boards", headers=headers).json()
    tn = next(b for b in boards if b["code"] == "TN_SSLC")
    assert (
        client.put(
            "/api/v1/auth/me", json={"boardId": tn["id"], "medium": "en"}, headers=headers
        ).status_code
        == 200
    )

    # Home: every subject open, each with its first topic available.
    tiles = client.get("/api/v1/subjects", headers=headers).json()
    assert len(tiles) == 5
    assert all(t["currentTopic"]["status"] == "available" for t in tiles)
    maths = tiles[0]
    first = maths["currentTopic"]["id"]
    detail = client.get(f"/api/v1/subjects/{maths['id']}", headers=headers).json()
    topics = [t for ch in detail["chapters"] for t in ch["topics"]]
    second = topics[1]["id"]
    assert topics[1]["status"] == "locked"

    # Start + lesson + "Not clear".
    assert (
        client.post(f"/api/v1/topics/{first}/start", headers=headers).json()["status"] == "active"
    )
    opened = client.get(f"/api/v1/topics/{first}/lesson", headers=headers).json()
    base = opened["lesson"] or opened["job"]["lesson"]
    client.put(
        f"/api/v1/lessons/{base['id']}/progress",
        json={"watchedSec": 60, "completed": True},
        headers=headers,
    )
    again = client.post(
        f"/api/v1/topics/{first}/not-clear", json={"lessonId": base["id"]}, headers=headers
    ).json()
    assert (again["lesson"] or again["job"]["lesson"])["style"] != "base"

    # Fail the quiz → still locked.
    attempt = client.post(f"/api/v1/topics/{first}/quiz-attempts", headers=headers).json()
    failed = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": _answers(attempt, 3)},
        headers=headers,
    ).json()
    assert failed["passed"] is False
    assert client.get(f"/api/v1/topics/{second}", headers=headers).status_code == 403

    # Pass with fresh questions → next topic unlocks.
    retry = client.post(f"/api/v1/topics/{first}/quiz-attempts", headers=headers).json()
    assert not {q["questionId"] for q in retry["questions"]} & {
        q["questionId"] for q in attempt["questions"]
    }
    passed = client.post(
        f"/api/v1/quiz-attempts/{retry['attemptId']}/submit",
        json={"answers": _answers(retry, 7)},
        headers=headers,
    ).json()
    assert passed["passed"] is True and passed["nextTopic"]["id"] == second
    assert client.get(f"/api/v1/topics/{second}", headers=headers).json()["status"] == "available"

    # Other subjects are untouched.
    science = client.get("/api/v1/subjects", headers=headers).json()[1]
    assert science["completedTopics"] == 0 and science["currentTopic"]["status"] == "available"
