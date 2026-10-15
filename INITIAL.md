# INITIAL.md - Personal Teacher Assistant for 10th — Product Definition

> An Android app that coaches 10th-standard students through their public-exam syllabus one topic at a time — with practical video/audio lessons, AI re-explanations in a new style whenever a topic isn't clear, and a fresh 60%-pass quiz that unlocks the next topic.

---

## PRODUCT

### Name
Personal Teacher Assistant for 10th

### Description
A mobile study companion for 10th-standard (SSLC / board exam) students. The syllabus is broken into
Subject → Chapter → Topic. A student studies **one topic at a time**:

1. Watch/listen to the topic's practical video or audio explanation.
2. If the student taps **"Not clear"**, the app generates a **new explanation in a different style**
   (real-life analogy, step-by-step, story, visual diagram walk-through, worked example…) as narrated
   slide-video and audio, until the student understands.
3. The student takes a **topic quiz**. Questions are **different on every attempt**. Scoring **≥ 60%**
   completes the topic and unlocks the next one.
4. While a topic is in progress, **all other topics (including other subjects) stay locked** — the
   student finishes what they started before moving on.

The home screen is a **subject tile grid** (Tamil, English, Maths, Science, Social Science…) using calm,
**flat, solid, low-saturation colours** chosen for focus — **no gradients**.

The platform supports **multiple boards** and **English + regional-language mediums**. MVP launches with
**Tamil Nadu State Board (Samacheer Kalvi)** content in English and Tamil medium.

### Target User
10th-standard students preparing for state/central board public exams (primary), plus their parents
(progress view) and content admins/teachers (admin panel).

### Type
- [x] SaaS (Software as a Service) — Android-first mobile app + API + admin web panel

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+
- [x] Background worker for AI content jobs (Celery or RQ + Redis)
- [x] FFmpeg for rendering narrated slide videos

### Mobile App (student + parent)
- [x] React Native + Expo + TypeScript (Android first, iOS-ready)
- [x] expo-av / expo-video for playback, expo-file-system for offline downloads
- [x] Expo Notifications for push

### Admin Web Panel
- [x] React + Vite + TypeScript + Chakra UI (template default web stack)

### Database
- [x] PostgreSQL + SQLAlchemy + Alembic

### Authentication
- [x] Google Sign-In only (no phone OTP / SMS)
- [x] JWT access + refresh tokens

### UI Framework
- [x] React Native Paper (Material Design 3, custom flat focus theme — no gradients)

### AI Services
- [x] LLM (OpenAI API, structured JSON outputs) — explanation scripts in multiple teaching styles, quiz question generation
- [x] Text-to-Speech supporting English + Tamil (e.g. Google Cloud TTS / Azure TTS) — configurable provider
- [x] Object storage for generated media (S3-compatible: AWS S3 / Cloudflare R2)

### Payments
- [ ] None for now (free product; monetisation post-MVP)

---

## MODULES

### Module 1: Authentication (Required)

**Description:** Student, parent and admin sign-in via Google.

**Models:**
- User: id, email, full_name, role (student | parent | admin), board_id, medium (en | ta | …), oauth_provider, is_active, is_verified, created_at
- RefreshToken: id, user_id, token_hash, expires_at, revoked

**API Endpoints:**
- POST /api/v1/auth/google - Exchange Google ID token for app tokens (creates user if new)
- POST /api/v1/auth/dev-login - Development only (ENVIRONMENT=development): sign in as a seeded test user without Google; returns 404 in production
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/logout - Revoke refresh token
- GET /api/v1/auth/me - Current user profile
- PUT /api/v1/auth/me - Update profile (name, board, medium)

**Mobile Screens:**
- Welcome / Login (Sign in with Google)
- Onboarding: choose board + medium
- Profile & settings

---

### Module 2: Curriculum (Boards, Subjects, Chapters, Topics)

**Description:** The syllabus tree and the subject tile home screen.

**Models:**
- Board: id, code (TN_SSLC, CBSE…), name, is_active
- Subject: id, board_id, name, tile_color (solid hex from focus palette), icon, display_order
- Chapter: id, subject_id, title, display_order
- Topic: id, chapter_id, title, learning_objectives (text), display_order, is_published
- TopicTranslation: id, topic_id, medium, title, learning_objectives

**API Endpoints:**
- GET /api/v1/boards - List boards
- GET /api/v1/subjects - Subjects for the student's board, with progress % and lock state
- GET /api/v1/subjects/{id}/chapters - Chapters + topics with status (locked / active / completed)
- GET /api/v1/topics/{id} - Topic detail (403 if locked for this student)

**Mobile Screens:**
- Home: subject tile grid (solid colours, progress ring per tile, lock badge)
- Subject detail: chapter list → topic list with locked/active/completed states

---

### Module 3: Learning (Lessons + AI Re-Explanation)

**Description:** Video/audio lessons per topic, and on-demand AI regeneration of a new-style explanation when the student taps "Not clear".

**Models:**
- Lesson: id, topic_id, medium, style (base | analogy | step_by_step | story | real_life | worked_example | visual), source (uploaded | ai_generated), script_text, audio_url, video_url, duration_sec, status (pending | generating | ready | failed), created_at
- LessonView: id, user_id, lesson_id, watched_sec, completed, created_at
- ClarityFeedback: id, user_id, topic_id, lesson_id, is_clear (bool), note, created_at
- GenerationJob: id, user_id, topic_id, requested_style, status, error, lesson_id, created_at, finished_at

**API Endpoints:**
- GET /api/v1/topics/{id}/lessons - Lessons for this topic in the student's medium
- POST /api/v1/topics/{id}/lessons/{lesson_id}/progress - Report watch progress
- POST /api/v1/topics/{id}/not-clear - Record feedback + queue a new-style explanation (picks a style the student hasn't seen yet; reuses a cached ready lesson of that style if one exists)
- GET /api/v1/generation-jobs/{id} - Poll job status
- POST /api/v1/topics/{id}/clear - Mark "I understood" → enables quiz

**Mobile Screens:**
- Topic lesson screen: video/audio toggle, player, "Not clear — explain differently" + "I understood, take quiz" buttons
- Generating state (friendly progress UI while the new explanation is produced; plays audio first when video is still rendering)

---

### Module 4: Quiz & Assessment

**Description:** Topic quizzes with fresh questions on every attempt; ≥ 60% passes the topic.

**Models:**
- Question: id, topic_id, medium, type (mcq | true_false | fill_blank), stem, options (JSON), correct_answer, explanation, difficulty, source (ai | admin), is_approved, created_at
- QuizAttempt: id, user_id, topic_id, score_pct, passed, started_at, submitted_at
- QuizAttemptQuestion: id, attempt_id, question_id, selected_answer, is_correct

**API Endpoints:**
- POST /api/v1/topics/{id}/quiz - Start attempt: returns N questions (default 10) **not previously served to this student**; tops up the pool via AI when unseen questions run low. Correct answers never sent to client.
- POST /api/v1/quiz-attempts/{id}/submit - Grade server-side, return score, per-question explanations, pass/fail
- GET /api/v1/topics/{id}/quiz-attempts - Attempt history

**Mobile Screens:**
- Quiz screen (one question per card, progress bar)
- Result screen: score, pass (unlocks next topic, celebration) / fail (review mistakes → "Explain again" or "Retry quiz")

---

### Module 5: Progress & Unlocking

**Description:** Enforces the one-topic-at-a-time rule and tracks progress.

**Models:**
- TopicProgress: id, user_id, topic_id, status (locked | active | completed), best_score_pct, attempts_count, started_at, completed_at
- StudyStreak: id, user_id, current_streak_days, longest_streak_days, last_study_date

**Business Rules:**
- A student has **at most one `active` topic** at any time.
- Topics within a subject unlock **sequentially** (chapter order → topic order).
- While a topic is active, every other topic — in any subject — is locked. The student can browse subject tiles but sees "Finish *&lt;active topic&gt;* first".
- A topic becomes `completed` only via a quiz attempt with score ≥ 60%. Completion frees the student to pick the next unlocked topic in any subject.
- Lock state is **enforced server-side** on lesson, quiz and topic endpoints, not just in the UI.

**API Endpoints:**
- GET /api/v1/progress - Overall + per-subject progress, active topic, streak
- POST /api/v1/topics/{id}/start - Start a topic (fails with 409 if another topic is active or topic is locked)

**Mobile Screens:**
- "Continue learning" card on home (resume active topic)
- Progress screen: per-subject completion, streak

---

### Module 6: Dashboard & Parent View

**Description:** Student and parent progress analytics.

**Models:**
- ParentLink: id, parent_user_id, student_user_id, invite_code, status (pending | accepted), created_at

**API Endpoints:**
- POST /api/v1/parent/link - Parent enters student's invite code
- GET /api/v1/parent/students - Linked students
- GET /api/v1/parent/students/{id}/report - Progress, weak topics, quiz trends, study time

**Mobile Screens:**
- Student dashboard (topics done, average score, weak topics)
- Parent home (linked students) and student report with charts
- Settings (medium, notifications, downloads)

---

### Module 7: Notifications

**Description:** Push reminders and streak nudges.

**Models:**
- DeviceToken: id, user_id, expo_push_token, platform, created_at
- NotificationLog: id, user_id, type, payload, sent_at

**API Endpoints:**
- POST /api/v1/devices - Register push token
- DELETE /api/v1/devices/{id} - Unregister

**Behaviour:** daily study reminder, "your new explanation is ready", streak-at-risk, parent weekly summary.

---

### Module 8: Offline Downloads

**Description:** Download lessons for offline study.

**API Endpoints:**
- GET /api/v1/lessons/{id}/download - Short-lived signed URL for media

**Mobile:** download manager in expo-file-system; offline quiz is **not** allowed (quizzes need server-side grading and fresh questions); progress sync on reconnect.

---

### Module 9: Admin Panel (Web)

**Description:** Admin-only content and user management.

**API Endpoints:**
- CRUD /api/v1/admin/boards, /subjects, /chapters, /topics
- POST /api/v1/admin/topics/{id}/lessons - Upload base video/audio
- GET /api/v1/admin/questions?status=pending - Review AI questions; PUT to approve/edit/reject
- GET /api/v1/admin/lessons?source=ai_generated - Review AI explanations; flag/remove
- GET /api/v1/admin/users - List users; PUT /api/v1/admin/users/{id} - Activate/deactivate
- GET /api/v1/admin/stats - Active students, topic pass rates, "not clear" hotspots, AI generation cost

**Pages:**
- /admin - Dashboard
- /admin/curriculum - Syllabus tree editor
- /admin/content - Lessons & AI content review
- /admin/questions - Question bank review
- /admin/users - User management

---

## MVP SCOPE

### Must Have (MVP)
- [x] Google sign-in, board & medium onboarding
- [x] Subject tile home screen (flat focus colours) + sequential topic lock per subject (first topic of every subject open; pass 60% to unlock the next)
- [x] Lesson video/audio player
- [x] AI re-explain on "Not clear" (LLM script → TTS → slide video)
- [x] AI quiz with fresh questions every attempt and 60% pass gate
- [x] TN State Board (Samacheer) content, English + Tamil medium
- [x] Minimal admin panel to load curriculum and base lessons

### Nice to Have (Post-MVP)
- [ ] Parent / analytics view
- [ ] Push notifications & streaks
- [ ] Offline downloads
- [ ] Additional boards (CBSE, other states) and mediums
- [ ] Payments / premium plans
- [ ] iOS release

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] Student can sign in with Google
- [ ] JWT access/refresh flow works; tokens stored in expo-secure-store
- [ ] Unauthenticated users are routed to login

### Curriculum & Progress
- [ ] Home shows subject tiles for the student's board in solid colours (no gradients)
- [ ] Only one topic can be active at a time; starting another returns 409
- [ ] Locked topics' lessons and quizzes return 403 from the API
- [ ] Next topic unlocks immediately after a passing quiz

### Learning
- [ ] Lessons play as video or audio in the student's medium
- [ ] "Not clear" produces a new explanation in a style the student hasn't seen for that topic
- [ ] Generated explanation (audio) is ready in < 60 s; video follows when rendered
- [ ] Previously generated lessons of a style are reused (cached) across students

### Quiz
- [ ] Each attempt serves questions the student has not seen before for that topic
- [ ] Correct answers are never present in the quiz-start response
- [ ] Score ≥ 60% marks topic completed; < 60% shows mistakes with explanations
- [ ] AI-generated questions are validated (single correct answer, options distinct) before use

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+
- [ ] Mobile & admin TypeScript strict mode passes
- [ ] Docker builds and runs successfully (api, worker, postgres, redis)
- [ ] Android build via EAS succeeds

---

## SPECIAL REQUIREMENTS

### Security & Safety
- [x] Rate limiting on auth endpoints
- [x] Input validation on all endpoints
- [x] SQL injection prevention (ORM only)
- [x] XSS prevention in admin panel
- [x] Google ID token verified server-side
- [x] Minors' data: collect minimum PII, no public profiles, parent link requires student-issued code
- [x] AI output guardrails: syllabus-grounded prompts, age-appropriate content, admin review queue

### Integrations
- [x] OpenAI API (explanations + questions)
- [x] TTS provider with Tamil support
- [x] Object storage (S3 / R2) + signed URLs
- [x] Expo push notifications
- [ ] Payments (none for MVP)

### Design
- [x] Flat, solid, calm colours (soft blues, greens, muted teal, warm neutral background); **no gradients**
- [x] Large readable type, high contrast (WCAG AA), minimal distractions on lesson & quiz screens

---

## AGENTS

> These 6 agents will build your product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | All database models |
| BACKEND-AGENT | Builds API endpoints, AI pipeline, workers | All modules' backends |
| FRONTEND-AGENT | Creates mobile screens + admin web pages | React Native app, admin panel |
| DEVOPS-AGENT | Docker, CI/CD, EAS builds, environments | Infrastructure |
| TEST-AGENT | Writes unit and integration tests | All code |
| REVIEW-AGENT | Security and code quality audit | All code |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/personal-teacher-assistant-prp.md
```
