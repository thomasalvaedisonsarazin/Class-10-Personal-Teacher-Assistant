"""Idempotent seed data: boards, TN SSLC sample curriculum (en + ta) and dev users.

Run from ``backend/``::

    python -m app.seed

Running it repeatedly is safe: rows are looked up by natural keys
(board code, display_order, medium, email) and updated in place.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    Board,
    Chapter,
    ChapterTranslation,
    Medium,
    Subject,
    SubjectTranslation,
    Topic,
    TopicTranslation,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

TN_SSLC = "TN_SSLC"
CBSE = "CBSE"

DEV_STUDENT_EMAIL = "student@dev.local"
DEV_PARENT_EMAIL = "parent@dev.local"


@dataclass(frozen=True)
class TopicSeed:
    """Seed definition of a topic (English + Tamil)."""

    title_en: str
    objectives_en: str
    title_ta: str
    objectives_ta: str


@dataclass(frozen=True)
class ChapterSeed:
    """Seed definition of a chapter and its topics."""

    title_en: str
    title_ta: str
    topics: tuple[TopicSeed, ...]


@dataclass(frozen=True)
class SubjectSeed:
    """Seed definition of a subject tile and its chapters."""

    name_en: str
    name_ta: str
    tile_color: str
    icon: str
    chapters: tuple[ChapterSeed, ...]


@dataclass
class SeedStats:
    """Counts of rows created (not updated) by a seed run."""

    created: dict[str, int] = field(default_factory=dict)

    def bump(self, kind: str) -> None:
        """Increment the created-counter for ``kind``."""
        self.created[kind] = self.created.get(kind, 0) + 1


BOARDS: tuple[tuple[str, str, bool], ...] = (
    (TN_SSLC, "Tamil Nadu State Board – SSLC", True),
    (CBSE, "Central Board of Secondary Education", False),
)

TN_SUBJECTS: tuple[SubjectSeed, ...] = (
    SubjectSeed(
        name_en="Mathematics",
        name_ta="கணிதம்",
        tile_color="#3B6EA5",
        icon="calculator-variant",
        chapters=(
            ChapterSeed(
                title_en="Relations and Functions",
                title_ta="உறவுகளும் சார்புகளும்",
                topics=(
                    TopicSeed(
                        "Ordered Pairs and Cartesian Product",
                        "Define ordered pairs; find the Cartesian product A × B of two sets "
                        "and represent it with arrow diagrams and graphs.",
                        "வரிசைச் சோடிகளும் கார்டீசியன் பெருக்கலும்",
                        "வரிசைச் சோடிகளை வரையறுத்தல்; இரு கணங்களின் கார்டீசியன் பெருக்கல் "
                        "A × B ஐக் கண்டு அம்புக்குறி படம் மற்றும் வரைபடம் மூலம் குறித்தல்.",
                    ),
                    TopicSeed(
                        "Relations",
                        "Understand a relation as a subset of A × B; identify domain, "
                        "co-domain and range of a relation.",
                        "உறவுகள்",
                        "A × B இன் உட்கணமாக உறவைப் புரிந்துகொள்ளுதல்; உறவின் மதிப்பகம், "
                        "துணை மதிப்பகம், வீச்சு ஆகியவற்றைக் கண்டறிதல்.",
                    ),
                    TopicSeed(
                        "Functions and their Representations",
                        "Recognise functions; represent them as arrow diagrams, tables, ordered "
                        "pairs and graphs; apply the vertical line test.",
                        "சார்புகளும் அவற்றின் குறியீடுகளும்",
                        "சார்புகளை அடையாளம் காணுதல்; அம்புக்குறி படம், அட்டவணை, வரிசைச் சோடி, "
                        "வரைபடம் மூலம் குறித்தல்; செங்குத்துக்கோடு சோதனையைப் பயன்படுத்துதல்.",
                    ),
                ),
            ),
            ChapterSeed(
                title_en="Numbers and Sequences",
                title_ta="எண்களும் தொடர்வரிசைகளும்",
                topics=(
                    TopicSeed(
                        "Euclid's Division Lemma and Algorithm",
                        "State Euclid's division lemma and use the division algorithm to find "
                        "the HCF of positive integers.",
                        "யூக்ளிடின் வகுத்தல் துணைத்தேற்றமும் வழிமுறையும்",
                        "யூக்ளிடின் வகுத்தல் துணைத்தேற்றத்தைக் கூறி, வகுத்தல் வழிமுறை மூலம் "
                        "மிகப்பெரிய பொது வகுத்தியைக் கண்டறிதல்.",
                    ),
                    TopicSeed(
                        "Fundamental Theorem of Arithmetic",
                        "Express composite numbers as a unique product of primes and use it "
                        "to find HCF and LCM.",
                        "அடிப்படை எண்ணியல் தேற்றம்",
                        "பகு எண்களைப் பகா எண்களின் தனித்த பெருக்கற்பலனாக எழுதி, மீ.பொ.வ மற்றும் மீ.சி.ம காணுதல்.",
                    ),
                    TopicSeed(
                        "Arithmetic Progression",
                        "Identify an AP, find its nth term and the sum of the first n terms, "
                        "and solve everyday problems using APs.",
                        "கூட்டுத் தொடர்வரிசை",
                        "கூட்டுத் தொடர்வரிசையை அடையாளம் கண்டு, n ஆவது உறுப்பு மற்றும் முதல் n "
                        "உறுப்புகளின் கூடுதலைக் கண்டு அன்றாடக் கணக்குகளைத் தீர்த்தல்.",
                    ),
                ),
            ),
        ),
    ),
    SubjectSeed(
        name_en="Science",
        name_ta="அறிவியல்",
        tile_color="#4F8A6B",
        icon="flask-outline",
        chapters=(
            ChapterSeed(
                title_en="Laws of Motion",
                title_ta="இயக்க விதிகள்",
                topics=(
                    TopicSeed(
                        "Inertia and Newton's First Law",
                        "Explain inertia and its types and state Newton's first law of motion "
                        "with everyday examples.",
                        "நிலைமமும் நியூட்டனின் முதல் விதியும்",
                        "நிலைமம் மற்றும் அதன் வகைகளை விளக்கி, நியூட்டனின் முதல் இயக்க விதியை "
                        "அன்றாட எடுத்துக்காட்டுகளுடன் கூறுதல்.",
                    ),
                    TopicSeed(
                        "Momentum and Newton's Second Law",
                        "Define linear momentum, derive F = ma from Newton's second law and "
                        "explain impulse.",
                        "உந்தமும் நியூட்டனின் இரண்டாம் விதியும்",
                        "நேர்க்கோட்டு உந்தத்தை வரையறுத்து, நியூட்டனின் இரண்டாம் விதியிலிருந்து "
                        "F = ma ஐத் தருவித்து, கணத்தாக்கை விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Newton's Third Law and Conservation of Momentum",
                        "State Newton's third law and the law of conservation of linear "
                        "momentum, with applications such as rocket propulsion.",
                        "நியூட்டனின் மூன்றாம் விதியும் உந்த மாறா விதியும்",
                        "நியூட்டனின் மூன்றாம் விதி மற்றும் நேர்க்கோட்டு உந்த மாறா விதியை "
                        "ராக்கெட் இயக்கம் போன்ற பயன்பாடுகளுடன் கூறுதல்.",
                    ),
                ),
            ),
            ChapterSeed(
                title_en="Optics",
                title_ta="ஒளியியல்",
                topics=(
                    TopicSeed(
                        "Refraction of Light",
                        "Describe refraction, state Snell's law and explain refractive index "
                        "with examples.",
                        "ஒளி விலகல்",
                        "ஒளி விலகலை விவரித்து, ஸ்நெல் விதியைக் கூறி, ஒளிவிலகல் எண்ணை "
                        "எடுத்துக்காட்டுகளுடன் விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Lenses and the Lens Formula",
                        "Trace images formed by convex and concave lenses and apply the lens "
                        "formula and magnification.",
                        "லென்சுகளும் லென்சு சமன்பாடும்",
                        "குவி மற்றும் குழி லென்சுகள் உருவாக்கும் பிம்பங்களை வரைந்து, லென்சு "
                        "சமன்பாடு மற்றும் உருப்பெருக்கத்தைப் பயன்படுத்துதல்.",
                    ),
                    TopicSeed(
                        "Human Eye and Defects of Vision",
                        "Describe the structure of the human eye, myopia and hypermetropia, "
                        "and how lenses correct them.",
                        "மனிதக் கண்ணும் பார்வைக் குறைபாடுகளும்",
                        "மனிதக் கண்ணின் அமைப்பு, கிட்டப்பார்வை, தூரப்பார்வை மற்றும் அவற்றை "
                        "லென்சுகள் மூலம் சரிசெய்யும் முறையை விவரித்தல்.",
                    ),
                ),
            ),
        ),
    ),
    SubjectSeed(
        name_en="Social Science",
        name_ta="சமூக அறிவியல்",
        tile_color="#3E8C8C",
        icon="earth",
        chapters=(
            ChapterSeed(
                title_en="Outbreak of World War I and Its Aftermath",
                title_ta="முதல் உலகப்போர் வெடித்தலும் அதன் பின்விளைவுகளும்",
                topics=(
                    TopicSeed(
                        "Causes of the First World War",
                        "Explain the alliances, militarism, imperialism and nationalism that "
                        "led to the First World War.",
                        "முதல் உலகப்போருக்கான காரணங்கள்",
                        "முதல் உலகப்போருக்கு வழிவகுத்த கூட்டணிகள், இராணுவவாதம், "
                        "ஏகாதிபத்தியம், தேசியவாதம் ஆகியவற்றை விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Course of the War",
                        "Trace the major fronts and turning points of the war and India's "
                        "role in it.",
                        "போரின் போக்கு",
                        "போரின் முக்கியப் போர்முனைகள், திருப்புமுனைகள் மற்றும் அதில் இந்தியாவின் பங்கை அறிதல்.",
                    ),
                    TopicSeed(
                        "Treaty of Versailles and the League of Nations",
                        "Describe the terms of the Treaty of Versailles and the formation, "
                        "work and failure of the League of Nations.",
                        "வெர்சாய் உடன்படிக்கையும் பன்னாட்டு சங்கமும்",
                        "வெர்சாய் உடன்படிக்கையின் விதிமுறைகள், பன்னாட்டு சங்கத்தின் தோற்றம், "
                        "பணிகள் மற்றும் தோல்வியை விவரித்தல்.",
                    ),
                ),
            ),
            ChapterSeed(
                title_en="India – Location, Relief and Drainage",
                title_ta="இந்தியா – அமைவிடம், நிலத்தோற்றம் மற்றும் வடிகாலமைப்பு",
                topics=(
                    TopicSeed(
                        "Location and Extent of India",
                        "Locate India using latitudes and longitudes and explain its size, "
                        "neighbours and Standard Time.",
                        "இந்தியாவின் அமைவிடமும் பரப்பும்",
                        "அட்சக் கோடுகள், தீர்க்கக் கோடுகள் மூலம் இந்தியாவின் அமைவிடம், பரப்பு, "
                        "அண்டை நாடுகள், இந்தியத் திட்ட நேரம் ஆகியவற்றை விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Physiographic Divisions of India",
                        "Describe the Himalayas, Northern Plains, Peninsular Plateau, coastal "
                        "plains and islands.",
                        "இந்தியாவின் இயற்கை அமைப்புப் பிரிவுகள்",
                        "இமயமலை, வடபெரும் சமவெளி, தீபகற்ப பீடபூமி, கடற்கரைச் சமவெளிகள், "
                        "தீவுகள் ஆகியவற்றை விவரித்தல்.",
                    ),
                    TopicSeed(
                        "Drainage – Himalayan and Peninsular Rivers",
                        "Compare Himalayan and Peninsular rivers and name the major river "
                        "systems including the Kaveri.",
                        "வடிகாலமைப்பு – இமயமலை மற்றும் தீபகற்ப ஆறுகள்",
                        "இமயமலை ஆறுகளையும் தீபகற்ப ஆறுகளையும் ஒப்பிட்டு, காவிரி உள்ளிட்ட "
                        "முக்கிய ஆற்று அமைப்புகளைக் குறிப்பிடுதல்.",
                    ),
                ),
            ),
        ),
    ),
    SubjectSeed(
        name_en="Tamil",
        name_ta="தமிழ்",
        tile_color="#7A6A9E",
        icon="book-open-page-variant",
        chapters=(
            ChapterSeed(
                title_en="Unit 1: Amudhendru Per (Language)",
                title_ta="இயல் 1: அமுதென்று பேர்",
                topics=(
                    TopicSeed(
                        "Poem: Annai Mozhiye",
                        "Appreciate the poem praising the Tamil language and explain its "
                        "imagery and figures of speech.",
                        "செய்யுள்: அன்னை மொழியே",
                        "தமிழ்மொழியைப் போற்றும் பாடலின் நயத்தையும் அணிகளையும் விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Prose: Tamil Sol Valam",
                        "Understand the richness of Tamil vocabulary and the many words used "
                        "for parts of plants.",
                        "உரைநடை: தமிழ்ச்சொல் வளம்",
                        "தமிழ்ச் சொல்வளத்தையும் தாவர உறுப்புகளுக்கான பல்வேறு சொற்களையும் அறிதல்.",
                    ),
                    TopicSeed(
                        "Grammar: Ezhuthu and Sol",
                        "Revise letters (ezhuthu) and words (sol) and identify their types.",
                        "இலக்கணம்: எழுத்து, சொல்",
                        "எழுத்து, சொல் ஆகியவற்றின் வகைகளை மீள்பார்வை செய்து அடையாளம் காணுதல்.",
                    ),
                ),
            ),
            ChapterSeed(
                title_en="Unit 2: Uyirin Osai (Nature)",
                title_ta="இயல் 2: உயிரின் ஓசை",
                topics=(
                    TopicSeed(
                        "Poem: Kaatrai Vaa!",
                        "Appreciate Bharathiyar's poem on the wind and explain its central idea.",
                        "செய்யுள்: காற்றே வா!",
                        "காற்றைப் பற்றிய பாரதியாரின் பாடலின் மையக்கருத்தை விளக்குதல்.",
                    ),
                    TopicSeed(
                        "Poem: Mullaippaattu",
                        "Understand the Sangam poem's depiction of the mullai landscape and rain.",
                        "செய்யுள்: முல்லைப்பாட்டு",
                        "முல்லை நிலத்தையும் மழையையும் சங்கப் பாடல் சித்தரிக்கும் விதத்தை அறிதல்.",
                    ),
                    TopicSeed(
                        "Grammar: Thogainilai Thodargal",
                        "Identify the types of thogainilai thodar with examples.",
                        "இலக்கணம்: தொகைநிலைத் தொடர்கள்",
                        "தொகைநிலைத் தொடர்களின் வகைகளை எடுத்துக்காட்டுகளுடன் அடையாளம் காணுதல்.",
                    ),
                ),
            ),
        ),
    ),
    SubjectSeed(
        name_en="English",
        name_ta="ஆங்கிலம்",
        tile_color="#B0745A",
        icon="alphabet-latin",
        chapters=(
            ChapterSeed(
                title_en="Unit 1",
                title_ta="அலகு 1",
                topics=(
                    TopicSeed(
                        "Prose: His First Flight",
                        "Read and understand Liam O'Flaherty's story of a young seagull's "
                        "first flight; answer comprehension questions.",
                        "உரைநடை: His First Flight",
                        "இளம் கடற்பறவையின் முதல் பறத்தல் பற்றிய கதையைப் படித்துப் புரிந்து "
                        "வினாக்களுக்கு விடையளித்தல்.",
                    ),
                    TopicSeed(
                        "Poem: Life",
                        "Appreciate Henry Van Dyke's poem 'Life' and identify its poetic devices.",
                        "செய்யுள்: Life",
                        "ஹென்றி வான் டைக்கின் 'Life' கவிதையின் கருத்தையும் கவிதை உத்திகளையும் அறிதல்.",
                    ),
                    TopicSeed(
                        "Supplementary: The Tempest",
                        "Narrate the story of Shakespeare's 'The Tempest' and describe its "
                        "main characters.",
                        "துணைப்பாடம்: The Tempest",
                        "ஷேக்ஸ்பியரின் 'The Tempest' கதையைக் கூறி, முக்கியக் கதாபாத்திரங்களை விவரித்தல்.",
                    ),
                ),
            ),
            ChapterSeed(
                title_en="Unit 2",
                title_ta="அலகு 2",
                topics=(
                    TopicSeed(
                        "Prose: The Night the Ghost Got In",
                        "Understand James Thurber's humorous story and the role of "
                        "misunderstanding in it.",
                        "உரைநடை: The Night the Ghost Got In",
                        "ஜேம்ஸ் தர்பரின் நகைச்சுவைக் கதையையும் அதில் தவறான புரிதலின் பங்கையும் அறிதல்.",
                    ),
                    TopicSeed(
                        "Poem: The Grumble Family",
                        "Appreciate Lucy Maud Montgomery's poem and its message about complaining.",
                        "செய்யுள்: The Grumble Family",
                        "முணுமுணுப்பைப் பற்றிய லூசி மாட் மாண்ட்கோமரியின் கவிதையின் செய்தியை அறிதல்.",
                    ),
                    TopicSeed(
                        "Supplementary: Zigzag",
                        "Narrate Asha Nehemiah's story 'Zigzag' about a talking bird and a "
                        "boy's adventure.",
                        "துணைப்பாடம்: Zigzag",
                        "பேசும் பறவையும் ஒரு சிறுவனின் சாகசமும் பற்றிய 'Zigzag' கதையைக் கூறுதல்.",
                    ),
                ),
            ),
        ),
    ),
)


def _upsert_board(db: Session, code: str, name: str, is_active: bool, stats: SeedStats) -> Board:
    """Create or update a board by ``code``."""
    board = db.scalar(select(Board).where(Board.code == code))
    if board is None:
        board = Board(code=code, name=name, is_active=is_active)
        db.add(board)
        stats.bump("boards")
    else:
        board.name = name
        board.is_active = is_active
    db.flush()
    return board


def _upsert_subject(
    db: Session, board: Board, order: int, seed: SubjectSeed, stats: SeedStats
) -> Subject:
    """Create or update a subject (keyed by board + display_order) and its translations."""
    subject = db.scalar(
        select(Subject).where(Subject.board_id == board.id, Subject.display_order == order)
    )
    if subject is None:
        subject = Subject(
            board_id=board.id,
            display_order=order,
            name=seed.name_en,
            tile_color=seed.tile_color,
            icon=seed.icon,
        )
        db.add(subject)
        stats.bump("subjects")
    else:
        subject.name = seed.name_en
        subject.tile_color = seed.tile_color
        subject.icon = seed.icon
    db.flush()
    for medium, name in ((Medium.en, seed.name_en), (Medium.ta, seed.name_ta)):
        tr = db.scalar(
            select(SubjectTranslation).where(
                SubjectTranslation.subject_id == subject.id, SubjectTranslation.medium == medium
            )
        )
        if tr is None:
            db.add(SubjectTranslation(subject_id=subject.id, medium=medium, name=name))
            stats.bump("subject_translations")
        else:
            tr.name = name
    return subject


def _upsert_chapter(
    db: Session, subject: Subject, order: int, seed: ChapterSeed, stats: SeedStats
) -> Chapter:
    """Create or update a chapter (keyed by subject + display_order) and its translations."""
    chapter = db.scalar(
        select(Chapter).where(Chapter.subject_id == subject.id, Chapter.display_order == order)
    )
    if chapter is None:
        chapter = Chapter(subject_id=subject.id, display_order=order, title=seed.title_en)
        db.add(chapter)
        stats.bump("chapters")
    else:
        chapter.title = seed.title_en
    db.flush()
    for medium, title in ((Medium.en, seed.title_en), (Medium.ta, seed.title_ta)):
        tr = db.scalar(
            select(ChapterTranslation).where(
                ChapterTranslation.chapter_id == chapter.id, ChapterTranslation.medium == medium
            )
        )
        if tr is None:
            db.add(ChapterTranslation(chapter_id=chapter.id, medium=medium, title=title))
            stats.bump("chapter_translations")
        else:
            tr.title = title
    return chapter


def _upsert_topic(
    db: Session, chapter: Chapter, order: int, seed: TopicSeed, stats: SeedStats
) -> Topic:
    """Create or update a published topic (keyed by chapter + display_order) + translations."""
    topic = db.scalar(
        select(Topic).where(Topic.chapter_id == chapter.id, Topic.display_order == order)
    )
    if topic is None:
        topic = Topic(
            chapter_id=chapter.id,
            display_order=order,
            title=seed.title_en,
            learning_objectives=seed.objectives_en,
            is_published=True,
        )
        db.add(topic)
        stats.bump("topics")
    else:
        topic.title = seed.title_en
        topic.learning_objectives = seed.objectives_en
        topic.is_published = True
    db.flush()
    variants = (
        (Medium.en, seed.title_en, seed.objectives_en),
        (Medium.ta, seed.title_ta, seed.objectives_ta),
    )
    for medium, title, objectives in variants:
        tr = db.scalar(
            select(TopicTranslation).where(
                TopicTranslation.topic_id == topic.id, TopicTranslation.medium == medium
            )
        )
        if tr is None:
            db.add(
                TopicTranslation(
                    topic_id=topic.id, medium=medium, title=title, learning_objectives=objectives
                )
            )
            stats.bump("topic_translations")
        else:
            tr.title = title
            tr.learning_objectives = objectives
    return topic


def _ensure_user(
    db: Session,
    email: str,
    full_name: str,
    role: UserRole,
    board: Board | None,
    medium: Medium | None,
    stats: SeedStats,
) -> User:
    """Create a dev user if missing (existing users are left untouched)."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            board_id=board.id if board is not None else None,
            medium=medium,
            oauth_provider="dev",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        stats.bump("users")
    return user


def seed(db: Session, *, include_dev_users: bool | None = None) -> SeedStats:
    """Seed boards, the TN SSLC sample curriculum and (in development) dev users.

    Args:
        db: An open session. The caller is responsible for committing.
        include_dev_users: Force dev-user creation on/off. Defaults to
            ``settings.ENVIRONMENT == "development"``.

    Returns:
        Counts of rows created during this run (empty on a re-run).
    """
    stats = SeedStats()
    boards = {code: _upsert_board(db, code, name, active, stats) for code, name, active in BOARDS}
    tn = boards[TN_SSLC]

    for s_order, subject_seed in enumerate(TN_SUBJECTS, start=1):
        subject = _upsert_subject(db, tn, s_order, subject_seed, stats)
        for c_order, chapter_seed in enumerate(subject_seed.chapters, start=1):
            chapter = _upsert_chapter(db, subject, c_order, chapter_seed, stats)
            for t_order, topic_seed in enumerate(chapter_seed.topics, start=1):
                _upsert_topic(db, chapter, t_order, topic_seed, stats)

    if include_dev_users is None:
        include_dev_users = settings.ENVIRONMENT == "development"
    if include_dev_users:
        _ensure_user(db, DEV_STUDENT_EMAIL, "Dev Student", UserRole.student, tn, Medium.en, stats)
        _ensure_user(db, DEV_PARENT_EMAIL, "Dev Parent", UserRole.parent, None, None, stats)

    db.flush()
    return stats


def main() -> None:
    """Entry point for ``python -m app.seed``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as db:
        try:
            stats = seed(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Seeding failed")
            raise
    if stats.created:
        logger.info("Seed complete. Created: %s", stats.created)
    else:
        logger.info("Seed complete. Nothing new to create (already seeded).")


if __name__ == "__main__":
    main()
