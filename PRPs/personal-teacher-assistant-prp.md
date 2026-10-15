# PRP: Personal Teacher Assistant for 10th

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | Personal Teacher Assistant for 10th |
| **Type** | SaaS — Android app (Expo) + FastAPI API + admin web panel |
| **Version** | 1.0 |
| **Created** | 2026-10-13 |
| **Complexity** | High (AI media pipeline, mobile + web clients, strict progression rules) |
| **Source** | INITIAL.md, CLAUDE.md |

---

## PRODUCT OVERVIEW

**Description:** A study companion for 10th-standard public-exam students. The syllabus (Board → Subject → Chapter → Topic) is studied one topic at a time. Each topic has practical video/audio lessons; tapping **"Not clear"** generates a new explanation in a different teaching style (LLM script → TTS audio → narrated slide video). A topic quiz with **fresh questions every attempt** must be passed at **≥ 60%** to complete the topic. While a topic is active, every other topic is locked.

**Value Proposition:** Personal-tutor-style teaching that adapts until the student actually understands, with mastery verified before moving on — in the student's own medium (English / Tamil), at a fraction of tuition cost.

**MVP Scope (Phase 2A):**
- [ ] Google sign-in, board & medium onboarding
- [ ] Subject tile home (flat focus colours, no gradients) + one-active-topic / sequential lock
- [ ] Lesson video/audio player
- [ ] AI re-explain on "Not clear"
- [ ] AI quiz with unseen questions each attempt + 60% pass gate
- [ ] TN State Board (Samacheer) content, English + Tamil medium
- [ ] Minimal admin panel: curriculum CRUD, base lesson upload, AI content review

**Post-MVP (Phase 2B — build after MVP gate passes):**
- [ ] Parent / analytics view
- [ ] Push notifications & streaks
- [ ] Offline downloads
- [ ] Additional boards / mediums

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+, Pydantic v2 | skills/BACKEND.md |
| Background jobs | Celery + Redis | skills/BACKEND.md |
| Media render | FFmpeg (slides PNG + TTS audio → MP4), Pillow for slide images | — |
| Mobile | React Native + Expo SDK (expo-router) + TypeScript strict | skills/FRONTEND.md (adapted) |
| Mobile UI | React Native Paper (MD3) with custom flat focus theme | skills/FRONTEND.md (adapted) |
| Admin Web | React + Vite + TypeScript + Chakra UI | skills/FRONTEND.md |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 + Alembic | skills/DATABASE.md |
| Auth | Google Sign-In only (ID token verified server-side), JWT (HS256); dev-only login for local testing | skills/BACKEND.md |
| AI | OpenAI API (official `openai` SDK, Structured Outputs with JSON schema; model set via `LLM_MODEL`), TTS provider abstraction (Google Cloud TTS: en-IN, ta-IN) | — |
| Storage | S3-compatible (S3 / R2), signed URLs | skills/DEPLOYMENT.md |
| Testing | pytest + httpx, Jest + React Native Testing Library, Vitest + RTL (admin) | skills/TESTING.md |
| Deployment | Docker Compose (api, worker, postgres, redis), GitHub Actions, EAS Build | skills/DEPLOYMENT.md |

---

## DATABASE MODELS

All tables: `id` (int PK), `created_at`, `updated_at` unless noted. FKs indexed. Enums as PostgreSQL enums.

### Auth
- **User**: id, email (unique), full_name, role (`student|parent|admin`), board_id → Board (nullable until onboarding), medium (`en|ta`), oauth_provider (nullable), google_sub (unique, nullable), is_active, is_verified, created_at
- **RefreshToken**: id, user_id → User, token_hash (unique), expires_at, revoked, replaced_by_id (rotation chain)

### Curriculum
- **Board**: id, code (unique: `TN_SSLC`, `CBSE`), name, is_active
- **Subject**: id, board_id → Board, name, tile_color (hex, from palette), icon (MaterialCommunityIcons name), display_order — UNIQUE(board_id, display_order)
- **Chapter**: id, subject_id → Subject, title, display_order — UNIQUE(subject_id, display_order)
- **Topic**: id, chapter_id → Chapter, title, learning_objectives (text), display_order, is_published — UNIQUE(chapter_id, display_order)
- **TopicTranslation**: id, topic_id → Topic, medium, title, learning_objectives — UNIQUE(topic_id, medium)
- *(Subject/Chapter names also need translations: add `SubjectTranslation`, `ChapterTranslation` with the same shape.)*

### Learning
- **Lesson**: id, topic_id → Topic, medium, style (`base|analogy|step_by_step|story|real_life|worked_example|visual`), source (`uploaded|ai_generated`), script_text, slides_json (JSONB), audio_key, video_key, duration_sec, status (`pending|generating|audio_ready|ready|failed`), is_flagged, created_at
  - INDEX(topic_id, medium, style, status)
- **LessonView**: id, user_id, lesson_id, watched_sec, completed — UNIQUE(user_id, lesson_id)
- **ClarityFeedback**: id, user_id, topic_id, lesson_id, is_clear, note
- **GenerationJob**: id, user_id, topic_id, medium, requested_style, kind (`explanation|questions`), status (`queued|running|done|failed`), error, lesson_id (nullable), started_at, finished_at

### Quiz
- **Question**: id, topic_id, medium, type (`mcq|true_false|fill_blank`), stem, options (JSONB list), correct_answer, explanation, difficulty (1–3), source (`ai|admin`), is_approved, content_hash (UNIQUE with topic_id+medium — dedupe)
- **QuizAttempt**: id, user_id, topic_id, score_pct (nullable until submit), passed, started_at, submitted_at, expires_at
- **QuizAttemptQuestion**: id, attempt_id, question_id, position, selected_answer, is_correct — UNIQUE(attempt_id, question_id)
  - "Served questions" for a student = join QuizAttempt(user_id, topic_id) → QuizAttemptQuestion

### Progress
- **TopicProgress**: id, user_id, topic_id, status (`active|completed`), best_score_pct, attempts_count, started_at, completed_at — UNIQUE(user_id, topic_id)
  - **Partial unique index**: `UNIQUE(user_id) WHERE status = 'active'` → DB-level guarantee of one active topic
  - "locked" is derived, not stored
- **StudyStreak**: id, user_id (unique), current_streak_days, longest_streak_days, last_study_date

### Parent / Notifications (Phase 2B)
- **ParentLink**: id, parent_user_id, student_user_id, invite_code (unique, 8 chars, expires), status (`pending|accepted|revoked`)
- **DeviceToken**: id, user_id, expo_push_token (unique), platform
- **NotificationLog**: id, user_id, type, payload (JSONB), sent_at

**Total: 21 models** (incl. SubjectTranslation, ChapterTranslation)

---

## CORE BUSINESS LOGIC (single sources of truth)

### `services/progress_service.py` — locking
```
next_unlocked_topic(user, subject) = first published topic in subject (chapter order, topic order)
                                     whose TopicProgress is not completed

topic_state(user, topic):
  completed  → if TopicProgress.status == completed
  active     → if TopicProgress.status == active
  available  → if user has NO active topic AND topic == next_unlocked_topic(user, topic.subject)
  locked     → otherwise

start_topic(user, topic): requires state == available, else 409 (another active) / 403 (locked)
require_access(user, topic): state in {active, completed} else 403  ← used by lessons + quiz endpoints
complete_topic(user, topic, score): only called from quiz grading when score >= QUIZ_PASS_PCT
```
Completed topics remain re-watchable (review) but cannot be "started" again.

### `services/ai/explanation.py` — "Not clear" flow
1. Record ClarityFeedback(is_clear=false).
2. Choose style: first style in rotation order not yet viewed by this student for (topic, medium).
   If all seen → cycle again preferring least-recently-viewed.
3. Cache hit: existing Lesson(topic, medium, style, status in {audio_ready, ready}, not flagged) → return 200 with lesson.
4. Cache miss: create Lesson(pending) + GenerationJob(queued) → return **202** with job id.
5. Worker: LLM → JSON `{title, slides:[{heading, bullets[], narration}], summary}` (validated with Pydantic; retry once on invalid) → TTS each slide's narration → concat audio → upload → `audio_ready` → render slides (Pillow, flat palette, Noto Sans Tamil font) + FFmpeg → upload → `ready`.
6. Per-user rate limit: max 10 generations/day (config).

Prompt must include: board, subject, chapter, topic title + learning objectives, medium, target style definition, the previous explanation's summary (to avoid repeating), reading level for ~15-year-olds, "use local, everyday Indian examples", and "stay strictly within syllabus".

### `services/quiz_service.py` — fresh questions
1. `served_ids` = all question_ids ever served to this user for (topic).
2. Candidates = approved questions for (topic, medium) NOT IN served_ids.
3. If candidates < N (10): synchronously generate a batch of 15 via LLM (structured JSON), validate (exactly one correct answer, 4 distinct options for MCQ, answer ∈ options, non-empty explanation), dedupe by content_hash, auto-approve AI questions for MVP (`AI_QUESTIONS_AUTO_APPROVE=true`), flag for admin review.
4. Sample N with difficulty mix (≈ 4 easy, 4 medium, 2 hard), shuffle options per serve.
5. Response never includes `correct_answer` / `explanation`.
6. Submit: grade server-side, persist, `passed = score_pct >= QUIZ_PASS_PCT`; if passed → `complete_topic`. Return per-question correctness + explanation. Attempts expire after 60 min.
7. Background pre-warm: when a topic is started, enqueue question generation so the pool is ready before the quiz.

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/google | Verify Google ID token → tokens; create user if new (rate limited per IP) |
| POST | /api/v1/auth/dev-login | Dev only (ENVIRONMENT=development): sign in as seeded test user; 404 otherwise |
| POST | /api/v1/auth/refresh | Rotate refresh token |
| POST | /api/v1/auth/logout | Revoke refresh token |
| GET | /api/v1/auth/me | Current user |
| PUT | /api/v1/auth/me | Update name, board, medium |

**Mobile Screens (expo-router):**
| Route | Screen | Components |
|-------|--------|------------|
| /(auth)/login | LoginScreen | GoogleSignInButton, DevLoginButton (dev builds only) |
| /(auth)/onboarding | OnboardingScreen | BoardPicker, MediumPicker |
| /(app)/profile | ProfileScreen | ProfileForm, MediumSwitcher, LogoutButton |

---

### Module 2: Curriculum
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/boards | Active boards |
| GET | /api/v1/subjects | Student's board subjects + progress % + has_available flag |
| GET | /api/v1/subjects/{id}/chapters | Chapters with topics + per-topic state |
| GET | /api/v1/topics/{id} | Topic detail + state (localized to medium) |

**Mobile Screens:**
| Route | Screen | Components |
|-------|--------|------------|
| /(app)/ | HomeScreen | ContinueLearningCard, SubjectTileGrid, SubjectTile (solid colour, ProgressRing, LockBadge) |
| /(app)/subject/[id] | SubjectScreen | ChapterSection, TopicRow (locked/available/active/completed), StartTopicDialog |

---

### Module 3: Learning
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/topics/{id}/lessons | Lessons for topic in medium (signed media URLs) |
| POST | /api/v1/lessons/{id}/progress | Report watched_sec / completed |
| POST | /api/v1/topics/{id}/not-clear | Feedback + cached lesson (200) or queued job (202) |
| GET | /api/v1/generation-jobs/{id} | Job status + lesson when audio_ready/ready |
| POST | /api/v1/topics/{id}/clear | "I understood" → quiz enabled |

**Mobile Screens:**
| Route | Screen | Components |
|-------|--------|------------|
| /(app)/topic/[id] | LessonScreen | MediaModeToggle (Video/Audio), VideoPlayer, AudioPlayer, StyleChip, NotClearButton, UnderstoodButton |
| (overlay) | GeneratingOverlay | Calm progress indicator, "Preparing a new way to explain…", auto-plays audio when ready |

---

### Module 4: Quiz
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/topics/{id}/quiz | Start attempt with N unseen questions (no answers) |
| POST | /api/v1/quiz-attempts/{id}/submit | Grade, persist, unlock on pass |
| GET | /api/v1/topics/{id}/quiz-attempts | Attempt history |

**Mobile Screens:**
| Route | Screen | Components |
|-------|--------|------------|
| /(app)/quiz/[attemptId] | QuizScreen | QuestionCard, OptionButton, QuizProgressBar, SubmitDialog |
| /(app)/quiz/[attemptId]/result | ResultScreen | ScoreCircle, PassBanner / RetryBanner, MistakeReviewList, ExplainAgainButton, NextTopicButton |

---

### Module 5: Progress & Unlocking
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/topics/{id}/start | Start topic (403 locked, 409 another active) |
| GET | /api/v1/progress | Overall + per-subject progress, active topic, streak |

**Mobile Screens:**
| Route | Screen | Components |
|-------|--------|------------|
| /(app)/progress | ProgressScreen | SubjectProgressList, StreakCard, StatsRow |

---

### Module 6: Admin Panel (MVP-minimal) — web
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints (role = admin):**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | /api/v1/admin/boards | List / create boards |
| PUT/DELETE | /api/v1/admin/boards/{id} | Update / deactivate |
| GET/POST | /api/v1/admin/subjects | List / create |
| PUT/DELETE | /api/v1/admin/subjects/{id} | Update / delete |
| GET/POST | /api/v1/admin/chapters | List / create |
| PUT/DELETE | /api/v1/admin/chapters/{id} | Update / delete |
| GET/POST | /api/v1/admin/topics | List / create (with translations) |
| PUT/DELETE | /api/v1/admin/topics/{id} | Update / delete |
| POST | /api/v1/admin/curriculum/import | Bulk import syllabus JSON/CSV |
| POST | /api/v1/admin/topics/{id}/lessons | Upload base video/audio (multipart → S3) |
| GET | /api/v1/admin/lessons | Filter by source/flagged |
| PUT | /api/v1/admin/lessons/{id} | Flag / unflag |
| GET | /api/v1/admin/questions | Review queue |
| PUT | /api/v1/admin/questions/{id} | Approve / edit / reject |
| GET | /api/v1/admin/users | List users |
| PUT | /api/v1/admin/users/{id} | Activate / deactivate |
| GET | /api/v1/admin/stats | Students, pass rates, not-clear hotspots, AI job counts |

Admin login: Google Sign-In restricted to users with role=admin (seeded via CLI `python -m app.cli create-admin`).

**Admin Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | AdminLoginPage | GoogleLoginButton |
| /admin | DashboardPage | StatCard, HotspotTable |
| /admin/curriculum | CurriculumPage | SyllabusTree, TopicEditor, TranslationTabs, ImportDialog |
| /admin/content | ContentPage | LessonTable, MediaUpload, LessonPreview |
| /admin/questions | QuestionsPage | QuestionReviewTable, QuestionEditor |
| /admin/users | UsersPage | UserTable |

---

### Module 7: Parent & Analytics (Phase 2B)
**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/parent/invite | Student generates invite code |
| POST | /api/v1/parent/link | Parent redeems code |
| GET | /api/v1/parent/students | Linked students |
| GET | /api/v1/parent/students/{id}/report | Progress, weak topics, score trend, study time |

**Mobile Screens:** /(parent)/ ParentHomeScreen, /(parent)/student/[id] StudentReportScreen (charts via victory-native), /(app)/share-progress InviteCodeScreen

### Module 8: Notifications (Phase 2B)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/devices | Register Expo push token |
| DELETE | /api/v1/devices/{id} | Unregister |

Celery beat jobs: daily study reminder, streak-at-risk; event push: "new explanation ready".

### Module 9: Offline Downloads (Phase 2B)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/lessons/{id}/download | Short-lived signed URL |

Mobile: DownloadsScreen, DownloadButton; expo-file-system storage; LessonView progress queued and synced on reconnect. Quizzes online-only.

---

## MOBILE DESIGN SYSTEM (FRONTEND-AGENT)

`mobile/src/theme/palette.ts` — flat, calm, **no gradients**:
| Token | Hex | Use |
|-------|-----|-----|
| background | #F7F5F0 | warm off-white screen bg |
| surface | #FFFFFF | cards |
| textPrimary | #1F2A37 | dark slate |
| textSecondary | #556170 | |
| primary | #3B6EA5 | muted blue (actions) |
| success | #4F8A6B | sage green (passed) |
| warning | #C08A3E | muted amber (retry) |
| locked | #B8BEC6 | locked state |
| Subject tiles | #3B6EA5, #4F8A6B, #3E8C8C, #7A6A9E, #B0745A, #5C7A99 | Maths, Science, Social, Tamil, English, extra |

Rules: white text on tiles must pass WCAG AA; min touch target 48dp; Noto Sans + Noto Sans Tamil fonts; no animations on lesson/quiz screens beyond subtle transitions.

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: all 22 models, enums, partial unique index, Alembic initial migration, `database.py`, seed script (TN_SSLC board + 5 subjects + sample chapters/topics in en & ta)
- BACKEND-AGENT: `main.py`, `config.py` (pydantic-settings), router skeletons, auth deps (role guards), Celery app, storage/tts/llm/push service interfaces with fake implementations for dev/tests, `/health`
- FRONTEND-AGENT: Expo app (expo-router, TS strict, React Native Paper theme from palette, API client with token refresh, secure-store) + Vite admin app (Chakra, router, API client)
- DEVOPS-AGENT: `docker-compose.yml` (api, worker, postgres, redis, minio for local S3), Dockerfiles (api image includes ffmpeg + Noto fonts), `.env.example`, GitHub Actions (ruff, mypy, pytest, mobile/admin lint+typecheck), `eas.json`

**Validation Gate 1:** `pip install -r requirements.txt`, `alembic upgrade head`, `npm install` (mobile, admin), `docker-compose config`

**Phase 2A: MVP Modules (backend + frontend in parallel per module)**
- Auth: Google + dev-login endpoints ↔ Login/Onboarding screens + admin login
- Curriculum + Progress: progress_service + endpoints ↔ Home tiles, Subject screen
- Learning: lessons, not-clear, job worker pipeline ↔ Lesson screen + generating overlay
- Quiz: quiz_service + question generation ↔ Quiz + Result screens
- Admin: curriculum CRUD/import, upload, review ↔ admin pages

**Validation Gate 2:** `ruff check backend/`, `mypy backend/app`, `npm run lint && npm run type-check` (mobile, admin), MVP E2E smoke (seeded student: start topic → not-clear → quiz fail → quiz pass → next topic unlocks)

**Phase 2B: Post-MVP Modules** (only after Gate 2)
- Parent & analytics, Notifications + streaks, Offline downloads

**Phase 3: Quality (3 agents in parallel)**
- TEST-AGENT: pytest (unit for progress/quiz services; API integration; worker with fake LLM/TTS), Jest + RNTL for key screens, Vitest for admin; 80%+ backend coverage
- REVIEW-AGENT: security audit (Google ID token audience/expiry checks, dev-login disabled in production, token rotation, IDOR on topics/attempts/parent reports, answer leakage, signed URL expiry, prompt injection via admin fields), performance (N+1 on subjects/chapters listing, indexes)
- RESEARCH-AGENT: validate TTS Tamil voice quality/cost, Play Store policy for minors (Families policy), LLM cost per generated lesson

**Final Validation:** full test suite, `docker-compose up -d`, health check, `eas build -p android --profile preview`

---

## KEY TEST CASES (must exist)

- Only one active topic: concurrent `POST /topics/{a}/start` and `/topics/{b}/start` → one 200, one 409 (DB partial index)
- Locked topic → 403 on lessons, not-clear, quiz
- Quiz start never contains `correct_answer`
- Two consecutive attempts share zero question ids
- Score 59.9% → not passed; 60% → passed and next topic becomes available
- Not-clear returns a style the student hasn't seen; second student gets cached lesson (no new job)
- LLM returns invalid JSON → retry once → job `failed` with error, student sees friendly retry
- Google token with wrong audience / expired → 401; dev-login returns 404 when ENVIRONMENT=production
- Refresh token reuse after rotation → whole chain revoked
- Parent cannot read an unlinked student's report

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `cd mobile && npm install`, `cd admin && npm install`, `docker-compose config` |
| 2 | `ruff check backend/`, `mypy backend/app`, `cd mobile && npm run lint && npm run type-check`, `cd admin && npm run lint && npm run type-check` |
| 3 | `pytest --cov=app --cov-fail-under=80`, `cd mobile && npm test`, `cd admin && npm test` |
| Final | `docker-compose up -d`, `curl localhost:8000/health`, `eas build -p android --profile preview` |

---

## ENVIRONMENT VARIABLES

```env
# Database / queue
DATABASE_URL=postgresql://user:password@localhost:5432/personal_teacher_assistant
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
GOOGLE_CLIENT_ID=your-web-client-id
GOOGLE_ANDROID_CLIENT_ID=your-android-client-id

# AI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini        # any OpenAI chat model your key can access
TTS_PROVIDER=google         # google | azure | fake (dev/tests)
TTS_API_KEY=xxx
AI_GENERATIONS_PER_USER_PER_DAY=10
AI_QUESTIONS_AUTO_APPROVE=true

# Storage
S3_BUCKET=pta-media
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=xxx
S3_SECRET_ACCESS_KEY=xxx
SIGNED_URL_EXPIRE_SECONDS=3600

# Quiz
QUIZ_PASS_PCT=60
QUIZ_QUESTIONS_PER_ATTEMPT=10
QUIZ_ATTEMPT_EXPIRE_MINUTES=60

# Clients
EXPO_PUBLIC_API_URL=http://10.0.2.2:8000   # Android emulator → host
VITE_API_URL=http://localhost:8000
```

---

## RISKS & MITIGATIONS

| Risk | Mitigation |
|------|------------|
| AI explanation wrong/off-syllabus | Syllabus-grounded prompts, admin flagging, cached lessons reviewed over time |
| Generation latency | Deliver audio first; cache per (topic, medium, style); pre-warm questions on topic start |
| AI cost | Cache reuse across students, per-user daily limit, admin stats on job counts |
| Tamil TTS / font rendering | Use ta-IN neural voices, Noto Sans Tamil embedded in slide renderer, test fixtures in Tamil |
| Student stuck on hard topic (all other topics locked) | Unlimited retries + "Explain again" from result screen; admin hotspot report |
| Minors' data / Play Families policy | Minimal PII, no ads/third-party trackers, parent link by student consent code |

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/personal-teacher-assistant-prp.md
