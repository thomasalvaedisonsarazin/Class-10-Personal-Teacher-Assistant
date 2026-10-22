"""Exam practice endpoints: full-subject tests and model question papers (plan holders)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Request, UploadFile, status

from app.dependencies import DbSession, StudentUser
from app.rate_limit import limiter
from app.schemas.exam import (
    CreateModelPaperRequest,
    ExamOverviewOut,
    ModelPaperOut,
    PaperHtmlOut,
    SubjectTestOut,
    SubjectTestResultOut,
)
from app.schemas.quiz import SubmitAttemptRequest
from app.services import model_paper_service, subject_test_service
from app.workers.tasks import dispatch_paper_job

router = APIRouter(prefix="/api/v1", tags=["exams"])


@router.get("/subjects/{subject_id}/exam-practice", response_model=ExamOverviewOut)
def exam_overview(subject_id: int, db: DbSession, user: StudentUser) -> ExamOverviewOut:
    """Plan status, recent full-subject tests and model papers of a subject."""
    return model_paper_service.exam_overview(db, user, subject_id)


@router.post(
    "/subjects/{subject_id}/subject-tests",
    response_model=SubjectTestOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
def start_subject_test(
    request: Request, subject_id: int, db: DbSession, user: StudentUser
) -> SubjectTestOut:
    """Start (or resume) a test across every topic passed in the subject. No answers included."""
    return subject_test_service.start_subject_test(db, user, subject_id)


@router.post("/subject-tests/{test_id}/submit", response_model=SubjectTestResultOut)
def submit_subject_test(
    test_id: int, body: SubmitAttemptRequest, db: DbSession, user: StudentUser
) -> SubjectTestResultOut:
    """Grade a full-subject test on the server."""
    return subject_test_service.submit_subject_test(db, user, test_id, body.answers)


@router.post(
    "/subjects/{subject_id}/model-papers",
    response_model=ModelPaperOut,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
def create_model_paper(
    request: Request,
    subject_id: int,
    body: CreateModelPaperRequest,
    db: DbSession,
    user: StudentUser,
) -> ModelPaperOut:
    """Queue a board-pattern model paper (full syllabus or chosen chapters)."""
    paper = model_paper_service.create_model_paper(db, user, subject_id, body)
    dispatch_paper_job("generate", paper.id)
    db.refresh(paper)
    return model_paper_service.paper_out(paper)


@router.get("/model-papers/{paper_id}", response_model=ModelPaperOut)
def get_model_paper(paper_id: int, db: DbSession, user: StudentUser) -> ModelPaperOut:
    """A model paper; the answer key appears only after the answers are submitted."""
    return model_paper_service.get_model_paper(db, user, paper_id)


@router.get("/model-papers/{paper_id}/document", response_model=PaperHtmlOut)
def paper_document(
    paper_id: int,
    db: DbSession,
    user: StudentUser,
    kind: Annotated[Literal["paper", "key"], Query()] = "paper",
) -> PaperHtmlOut:
    """Printable HTML of the question paper, or of the answer key after submitting."""
    return model_paper_service.paper_document(db, user, paper_id, kind)


@router.post(
    "/model-papers/{paper_id}/answers",
    response_model=ModelPaperOut,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def submit_answers(
    request: Request,
    paper_id: int,
    db: DbSession,
    user: StudentUser,
    photos: Annotated[list[UploadFile], File()],
) -> ModelPaperOut:
    """Upload photos of the written answers; AI marking starts and the answer key opens."""
    paper = await model_paper_service.submit_answers(db, user, paper_id, photos)
    dispatch_paper_job("grade", paper.id)
    db.refresh(paper)
    return model_paper_service.paper_out(paper)
