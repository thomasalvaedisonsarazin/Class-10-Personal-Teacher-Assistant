"""Tamil Nadu State Board question-paper patterns (blueprints) for model papers.

Each pattern lists the parts of a paper: how many questions are printed, how many the
student answers, the marks for each, and whether the part is "either / or". Full
papers follow the public-exam pattern (9th uses the 10th pattern, as schools do);
"unit" papers are the shorter pattern used for chosen chapters.

Verify against the latest official blueprint before each academic year; changing a
pattern here only affects papers created afterwards (each paper stores its pattern id).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QuestionKind = Literal["mcq", "short", "long"]


@dataclass(frozen=True)
class PatternPart:
    """One part of a paper, e.g. Part II: 14 printed, answer any 10, 2 marks each."""

    label: str  # Roman numeral shown as "Part I"
    kind: QuestionKind
    printed: int  # questions printed (an either/or pair counts as one)
    answer: int  # questions the student answers
    marks: int  # marks per question
    either_or: bool = False
    compulsory_last: bool = False  # the last question of the part must be answered

    @property
    def total(self) -> int:
        """Marks this part contributes."""
        return self.answer * self.marks


@dataclass(frozen=True)
class ExamPattern:
    """A whole paper."""

    id: str
    total_marks: int
    duration_minutes: int
    parts: tuple[PatternPart, ...]

    @property
    def question_count(self) -> int:
        """Numbered questions on the paper."""
        return sum(p.printed for p in self.parts)


def _p(
    label: str, kind: QuestionKind, printed: int, answer: int, marks: int, **kw: bool
) -> PatternPart:
    return PatternPart(label, kind, printed, answer, marks, **kw)


# --- 9th / 10th (SSLC) --------------------------------------------------------------------

SSLC_100 = ExamPattern(  # Mathematics, Social Science, English
    "sslc_100",
    100,
    180,
    (
        _p("I", "mcq", 14, 14, 1),
        _p("II", "short", 14, 10, 2, compulsory_last=True),
        _p("III", "long", 14, 10, 5, compulsory_last=True),
        _p("IV", "long", 2, 2, 8, either_or=True),
    ),
)
SSLC_SCIENCE_75 = ExamPattern(  # theory paper; 25 marks are practicals
    "sslc_science_75",
    75,
    180,
    (
        _p("I", "mcq", 12, 12, 1),
        _p("II", "short", 10, 7, 2, compulsory_last=True),
        _p("III", "long", 10, 7, 4, compulsory_last=True),
        _p("IV", "long", 3, 3, 7, either_or=True),
    ),
)
SSLC_TAMIL_100 = ExamPattern(
    "sslc_tamil_100",
    100,
    180,
    (
        _p("I", "mcq", 15, 15, 1),
        _p("II", "short", 12, 9, 2),
        _p("III", "short", 9, 6, 3),
        _p("IV", "long", 5, 5, 5, either_or=True),
        _p("V", "long", 3, 3, 8, either_or=True),
    ),
)
SSLC_UNIT_50 = ExamPattern(
    "sslc_unit_50",
    50,
    90,
    (
        _p("I", "mcq", 7, 7, 1),
        _p("II", "short", 7, 5, 2, compulsory_last=True),
        _p("III", "long", 7, 5, 5, compulsory_last=True),
        _p("IV", "long", 1, 1, 8, either_or=True),
    ),
)
SSLC_SCIENCE_UNIT_40 = ExamPattern(
    "sslc_science_unit_40",
    40,
    90,
    (
        _p("I", "mcq", 7, 7, 1),
        _p("II", "short", 7, 5, 2, compulsory_last=True),
        _p("III", "long", 6, 4, 4, compulsory_last=True),
        _p("IV", "long", 1, 1, 7, either_or=True),
    ),
)

# --- 11th / 12th (HSC) --------------------------------------------------------------------

HSC_90 = ExamPattern(  # subjects without practicals, and language papers
    "hsc_90",
    90,
    180,
    (
        _p("I", "mcq", 20, 20, 1),
        _p("II", "short", 10, 7, 2, compulsory_last=True),
        _p("III", "short", 10, 7, 3, compulsory_last=True),
        _p("IV", "long", 7, 7, 5, either_or=True),
    ),
)
HSC_70 = ExamPattern(  # theory paper of subjects with practicals
    "hsc_70",
    70,
    180,
    (
        _p("I", "mcq", 15, 15, 1),
        _p("II", "short", 9, 6, 2, compulsory_last=True),
        _p("III", "short", 9, 6, 3, compulsory_last=True),
        _p("IV", "long", 5, 5, 5, either_or=True),
    ),
)
HSC_UNIT_50 = ExamPattern(
    "hsc_unit_50",
    50,
    90,
    (
        _p("I", "mcq", 10, 10, 1),
        _p("II", "short", 6, 4, 2, compulsory_last=True),
        _p("III", "short", 6, 4, 3, compulsory_last=True),
        _p("IV", "long", 4, 4, 5, either_or=True),
    ),
)

PATTERNS: dict[str, ExamPattern] = {
    p.id: p
    for p in (
        SSLC_100,
        SSLC_SCIENCE_75,
        SSLC_TAMIL_100,
        SSLC_UNIT_50,
        SSLC_SCIENCE_UNIT_40,
        HSC_90,
        HSC_70,
        HSC_UNIT_50,
    )
}

# 11th / 12th subjects whose theory paper is 70 marks (the rest is practicals).
HSC_PRACTICAL_SUBJECTS = frozenset(
    {
        "physics",
        "chemistry",
        "botany",
        "zoology",
        "bio-botany",
        "bio-zoology",
        "bio-chemistry",
        "microbiology",
        "computer science",
        "computer applications",
        "geography",
        "statistics",
        "nursing (general)",
        "nutrition and dietetics",
        "home science",
    }
)
LANGUAGE_SUBJECTS = frozenset({"tamil", "advanced tamil", "english", "communicative english"})


def pattern_for(grade: int, subject_name: str, scope: Literal["full", "chapters"]) -> ExamPattern:
    """The paper pattern for a class and subject (English subject name).

    Args:
        grade: Class (9-12; other classes use the nearest pattern family)
        subject_name: The subject's base (English) name, e.g. "Physics"
        scope: "full" for a public-exam paper, "chapters" for a unit paper
    """
    name = subject_name.strip().casefold()
    if grade >= 11:
        if scope == "chapters":
            return HSC_UNIT_50
        return HSC_70 if name in HSC_PRACTICAL_SUBJECTS else HSC_90
    science = name == "science"
    if scope == "chapters":
        return SSLC_SCIENCE_UNIT_40 if science else SSLC_UNIT_50
    if science:
        return SSLC_SCIENCE_75
    if name == "tamil":
        return SSLC_TAMIL_100
    return SSLC_100


def is_language_subject(subject_name: str) -> bool:
    """Language papers get grammar / poetry / prose / composition questions."""
    return subject_name.strip().casefold() in LANGUAGE_SUBJECTS


def duration_label(minutes: int) -> str:
    """Exam time in words, e.g. "3 hours", "1 hour 30 minutes"."""
    hours, rest = divmod(minutes, 60)
    label = f"{hours} hour{'s' if hours != 1 else ''}" if hours else ""
    if rest:
        label = f"{label} {rest} minutes".strip()
    return label
