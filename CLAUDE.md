# CLAUDE.md - Personal Teacher Assistant for 10th — Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** Personal Teacher Assistant for 10th
**Description:** Android app that coaches 10th-standard students topic-by-topic with practical video/audio lessons, AI re-explanations in new styles on "Not clear", and fresh quizzes with a 60% pass gate that unlocks the next topic.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+ (+ Celery/RQ worker, Redis, FFmpeg)
- Mobile: React Native + Expo + TypeScript (Android first)
- Admin Web: React + Vite + TypeScript + Chakra UI
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: Google Sign-In only (no phone OTP), JWT
- UI: React Native Paper (flat focus theme — no gradients)
- AI: OpenAI API (scripts + questions), TTS (English + Tamil), S3-compatible storage

---

## Project Structure

```
personal-teacher-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py            # User, RefreshToken
│   │   │   ├── curriculum.py      # Board, Subject, Chapter, Topic, TopicTranslation
│   │   │   ├── lesson.py          # Lesson, LessonView, ClarityFeedback, GenerationJob
│   │   │   ├── quiz.py            # Question, QuizAttempt, QuizAttemptQuestion
│   │   │   ├── progress.py        # TopicProgress, StudyStreak
│   │   │   ├── parent.py          # ParentLink
│   │   │   └── notification.py    # DeviceToken, NotificationLog
│   │   ├── schemas/
│   │   ├── routers/               # auth, curriculum, lessons, quiz, progress, parent, devices, admin
│   │   ├── services/
│   │   │   ├── progress_service.py    # lock/unlock rules (single source of truth)
│   │   │   ├── quiz_service.py
│   │   │   ├── ai/
│   │   │   │   ├── llm.py             # OpenAI client wrapper (structured JSON outputs)
│   │   │   │   ├── explanation.py     # style-based script generation
│   │   │   │   ├── questions.py       # question generation + validation
│   │   │   │   ├── tts.py             # provider-agnostic TTS
│   │   │   │   └── video_render.py    # slides + audio → mp4 (FFmpeg)
│   │   │   ├── storage.py
│   │   │   └── push.py
│   │   ├── workers/               # background jobs
│   │   └── auth/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── mobile/                        # Expo app (student + parent)
│   ├── app/                       # expo-router screens
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/              # API client
│   │   ├── context/
│   │   ├── theme/                 # focus palette (flat colours)
│   │   └── types/
│   ├── app.json
│   └── package.json
├── admin/                         # React + Vite admin panel
│   ├── src/
│   │   ├── components/, pages/, hooks/, services/, context/, types/
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_topic(db: Session, topic_id: int) -> Topic:
    pass

# ALWAYS add docstrings for public functions
def start_quiz_attempt(db: Session, user: User, topic_id: int) -> QuizAttempt:
    """
    Start a quiz attempt with questions this student has never been served.

    Args:
        db: Database session
        user: Current student
        topic_id: Topic being assessed

    Returns:
        Created QuizAttempt with its questions (no correct answers exposed)
    """
    pass
```

### TypeScript (Mobile + Admin)
```typescript
// ALWAYS define interfaces for props and data
interface Topic {
  id: number;
  chapterId: number;
  title: string;
  status: 'locked' | 'active' | 'completed';
  bestScorePct: number | null;
}

// NO any types allowed
const fetchTopic = async (id: number): Promise<Topic> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging` module
- ❌ Never store refresh tokens or secrets in plain text - hash them
- ❌ Never hardcode secrets or API keys - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never call the LLM/TTS synchronously inside a request handler for video generation - queue a job
- ❌ Never return `correct_answer` in a quiz-start response

### Mobile / Admin
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles - use React Native Paper theme / `StyleSheet` tokens (mobile), Chakra UI (admin)
- ❌ Never use gradients (`LinearGradient` etc.) - flat, solid focus colours only
- ❌ Never decide lock state only on the client - the API is the source of truth

---

## Module-Specific Rules

### Curriculum Module
- Hierarchy is Board → Subject → Chapter → Topic; ordering via `display_order`
- Subject `tile_color` must come from the approved focus palette in `mobile/src/theme/`
- All student-facing text has a per-medium variant (en, ta, …)

### Progress Module
- All subjects are always open; the **first topic of every subject** is available from the start
- Within a subject, topics unlock sequentially (chapter order, then topic order); a student may study several subjects at once
- `completed` is set **only** by a quiz attempt with `score_pct >= 60`
- All lock checks live in `progress_service.py` and are enforced on every topic/lesson/quiz endpoint

### Learning Module
- Lesson `style` must be one of: base, analogy, step_by_step, story, real_life, worked_example, visual
- Lessons have an explanation **language** (`en` / `ta` / `tanglish`) independent of the textbook medium; students switch it on the lesson screen (remembered in `users.lesson_language`); cache key = topic + language + style. Tanglish = Tamil sentences in Tamil script with English technical words, read by the Tamil voice. Quizzes still follow the medium
- The first lesson of every topic is the **story** style (a teacher-uploaded lesson, if any, comes first); students can also pick any style from the style chips
- "Not clear" picks a style the student has not yet seen for that topic; reuse a cached `ready` lesson of that style + medium before generating
- Each slide has a storybook **illustration** (gpt-image-2, `IMAGE_MODEL`; fixed style guide + Kavya/Arun character sheet, no text in images) generated in parallel with TTS; players show it with a slow pan/zoom; bullets appear in time with the narration (bullet k of n at `slideDuration * k / (n + 1)`, same rule in the video renderer and the mobile player); a failed picture only drops that scene's picture
- Generation pipeline: LLM script → TTS audio (deliver first) → slide video render (async)
- Every new lesson passes an AI fact-check (`fact_check_script`, CHECK_REASONING_EFFORT) that may correct slides; every AI question is answered independently (`verify_questions`) and dropped if it disagrees with its key; question batches are ~40/40/20 easy/medium/hard (at least one hard)
- Prompts must be grounded in the topic's learning objectives and the board syllabus, age-appropriate for ~15-year-olds, in the student's medium

### Quiz Module
- Default 10 questions per attempt; serve only questions not previously served to this student for that topic
- When unseen approved questions run low, generate more via AI and validate (one correct answer, distinct options, matches topic) before use
- Grading happens server-side only
- Pass mark constant: `QUIZ_PASS_PCT = 60` in config

### Notifications Module
- Study streak = consecutive India-time days with a lesson watched or a test submitted (`streak_service.record_study`)
- Pushes go through `notification_service.notify` only: per-user language (en/ta), de-duplicated via `NotificationLog` (daily reminder once per day, parent weekly once per week per child), dead Expo tokens removed
- Pass notifications run as a background task after the response; scheduled jobs run via Celery beat (6 pm IST reminders, Sunday 7 pm parent weekly) or `python -m app.cli send-reminders` / `send-parent-weekly`

### Offline Module
- Downloads (phone only) save the lesson audio, slide pictures and slide JSON under `Paths.document/offline-lessons/<lessonId>/` (no video, to save space); `offlineService` is the only place touching the file system
- When a lesson can't load, the lesson screen offers the saved copy; tests always need internet (fresh questions, server grading)

### Parent Module
- Parent can see a student only after the student shares an invite code
- Parents have read-only access

### Design
- Calm flat palette: muted blue, sage green, soft teal, warm off-white background, dark slate text
- WCAG AA contrast; large touch targets; minimal distractions on quiz screens
- Lesson screens use calm, purposeful animation synced to the narration (scene fade-in, emoji pop-in, bullets appearing with the voice); respect the OS "reduce motion" setting; still no gradients

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/topics`, `/lessons`, `/quiz-attempts`
- Return appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 202: Accepted (AI generation job queued)
  - 400: Bad Request
  - 401: Unauthorized
  - 403: Forbidden (topic locked / wrong role)
  - 404: Not Found
  - 409: Conflict (e.g. duplicate resource)
  - 429: Too Many Requests (auth / AI rate limits)

---

## Authentication

### Google Sign-In
- The only sign-in method (no phone OTP / SMS)
- Verify Google ID token server-side (audience = Android/Web client IDs)
- `POST /api/v1/auth/dev-login` works only with `DEV_LOGIN_ENABLED=true` and never in production (config refuses to start); production also refuses weak `SECRET_KEY`s (<32 chars or containing insecure/change-me)

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 30 days (mobile), rotated on use
- Algorithm: HS256
- Mobile stores tokens in `expo-secure-store`

### Roles
- `student`, `parent`, `admin` — enforce with dependencies on routers

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/personal_teacher_assistant
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# Google Sign-In
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_ANDROID_CLIENT_ID=your-android-client-id

# AI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-5.4-mini       # natural Tamil/Tanglish (chosen after a side-by-side test)
TTS_PROVIDER=google
TTS_API_KEY=xxx

# Storage
S3_BUCKET=pta-media
S3_ENDPOINT_URL=https://...
S3_ACCESS_KEY_ID=xxx
S3_SECRET_ACCESS_KEY=xxx

# Quiz
QUIZ_PASS_PCT=60
QUIZ_QUESTIONS_PER_ATTEMPT=10

# Mobile / Admin
EXPO_PUBLIC_API_URL=http://localhost:8000
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.workers worker --loglevel=info   # AI generation worker

# Mobile
cd mobile
npm install
npx expo start            # press "a" for Android
eas build -p android      # production build

# Admin
cd admin
npm install
npm run dev

# Docker (api, worker, postgres, redis)
docker-compose up -d

# Tests
pytest backend/tests -v
cd mobile && npm test
cd admin && npm test

# Linting / types
ruff check backend/
cd mobile && npm run lint && npm run type-check
cd admin && npm run lint && npm run type-check
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```
Modules: auth, curriculum, learning, quiz, progress, parent, notifications, offline, admin, ai

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React / React Native + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

> Note: skills/FRONTEND.md targets React web; for the mobile app apply the same TypeScript/component rules using React Native + Expo + React Native Paper equivalents.

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Backend models
- BACKEND-AGENT → API development + AI pipeline
- FRONTEND-AGENT → Mobile screens + admin panel
- TEST-AGENT → Testing
- REVIEW-AGENT → Code review
- DEVOPS-AGENT → Docker, CI/CD, EAS builds

Read agent definitions in `/agents/` folder.
