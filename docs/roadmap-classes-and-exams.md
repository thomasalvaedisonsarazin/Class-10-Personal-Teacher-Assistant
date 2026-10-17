# Roadmap — all school classes (TN + CBSE) and professional / competitive exams

_Written 2026-10-18. Status today: TN SSLC 10th app is live on our server, waiting for Google Play
identity verification. Estimates below are rough working time for the developer + Claude; they do not
include Google review times._

## 1. Decisions in one line

| Question | Recommendation |
|---|---|
| Classes 1–12, TN State Board + CBSE | **Same app** (`com.edsolution.teacherassistant`), add a *Course* (board + class + stream) level |
| CA, CMA, TET, TNPSC, SSC, banking… | **Separate Play app**, built from **the same codebase** (app variant) with its own server deployment |
| Order | Launch 10th → 9th/11th/12th TN → CBSE 6–12 → Classes 1–8 (child-safe mode) → exam app |

Why one school app: one listing collects all ratings, students carry their account into the next class,
parents manage children in different classes in one place, and every new Play app on a personal account
needs its own review plus a **12-tester / 14-day closed test**.

Why a separate exam app: adults vs school children (different store category, keywords, branding,
pricing ~₹299–999/month vs ₹99), very different features (timed full-length mocks, written answers,
ranks), and different content rules (law/tax change every year).

---

## 2. Phase A — many classes and boards in the school app

### 2.1 Data model
Today: `Board → Subject → Chapter → Topic`, and `users.board_id`. Change to:

```
Board (TN_STATE, CBSE)
  └─ Course (board + class + stream)   e.g. TN-10, TN-12-SCIENCE-BIO, CBSE-8
       └─ Subject → Chapter → Topic   (unchanged)
users.course_id   (replaces users.board_id)
```

- New table `courses`: `id, board_id, code (unique), grade (1–12), stream (nullable), name, name_ta,
  media (en/ta/hi), age_band (early / middle / secondary / senior), is_active, display_order`.
- `subjects.course_id` replaces `subjects.board_id`.
- Migration: create course `TN-10` from today's `TN_SSLC` board, move its subjects and every user — no
  data loss; 10th students see no change.
- `progress_service`, curriculum queries, parent reports and the admin import switch from board to course
  (one place each). The curriculum JSON gets `courseCode`, `grade`, `stream`.
- Tamil medium only where the board offers it (TN); CBSE gets English (+ Hindi later).

### 2.2 Student experience
- Onboarding: **Board → Class → Stream (11/12 only) → Medium**.
- **"Move to next class"** at year end (Profile, plus a prompt in May/June): progress of the old class is
  kept and viewable; the plan carries over.
- Lesson prompts already say "age-appropriate for ~15-year-olds" — make the age come from the course
  (Class 1 ≈ 6 years … Class 12 ≈ 17).
- Payments: a plan covers **every class of that student** (simple, fair when they move up). Optionally
  cheaper plans for Classes 1–5 later (`premium_junior`).

### 2.3 Age bands (same engine, different screens)

| Band | Classes | Lessons | Tests | Account |
|---|---|---|---|---|
| Early | 1–3 | 1–2 min, voice + pictures, very little text, tap-the-picture activities | picture choices, read aloud, no fail gate | **parent-led** |
| Middle | 4–7 | 3–4 min story lessons | 5–8 questions, 60% gate optional | **parent-led** |
| Secondary | 8–10 | as today | 10 questions, 60% gate | student (parent link optional) |
| Senior | 11–12 | longer worked examples, derivations, diagrams | harder mix, numericals, case-based | student |

### 2.4 Children under 13 and data protection (Classes 1–7)
- Selecting ages **under 13** in Play Console brings in Google's **Families policy**: only
  Families-compliant SDKs, no ads to children (we have none), minimal data, clear privacy for parents.
  Every SDK we use (Expo, Firebase Messaging, Google Sign-In, expo-iap) must be checked against the
  Families self-certified SDK list before we tick under-13.
- **Parent-led accounts** for young children: the parent signs up (Google/email), adds a child profile
  (first name + class only, no email for the child), and the child uses the app on the parent's phone or
  with a simple PIN. Payments always by the parent.
- **India DPDP Act 2023 + DPDP Rules 2025**: a "child" is anyone **under 18** — that already includes our
  10th students. The rules require **verifiable parental consent** before processing a child's data and
  forbid tracking/targeted ads to children; the obligations phase in over about 18 months from the rules'
  notification (Nov 2025). Plan: add a parent-consent step (parent's email/phone confirms) for every
  student account **before** that deadline. _Get a short review from a lawyer — this is not legal advice._

### 2.5 Syllabus data
- Same method as 10th: titles + learning objectives from contents pages / objective boxes, **no textbook
  text**, en + ta.
- Sources: TN textbooks (Classes 1–12, free PDFs from the TN textbook corporation site) and the **CBSE
  curriculum document + NCERT books** (Classes 6–12 first).
- Size: TN 1–12 + CBSE 6–12 ≈ 19 courses × 150–350 topics ≈ **4,000–5,000 topics**. Lessons are made only
  when a topic is first opened, so unused topics cost nothing.

### 2.6 Effort (rough)

| Work | Time |
|---|---|
| Course level: model, migration, onboarding, admin, parent report, tests | 1–1.5 weeks |
| Each new syllabus file (you provide the PDFs) | 1–2 days per class/board |
| Senior band (11–12) prompt + question tuning, numerical answers | 1 week |
| Early/middle bands: parent-led accounts, child profiles, picture activities | 2–3 weeks |
| Parental consent flow (DPDP) | 3–5 days |

---

## 3. Phase B — exam engine (shared by both apps)

### 3.1 New concepts
```
Exam (CA Foundation, CA Inter, CA Final, CMA Inter, TET Paper 1/2, TNPSC Group 4, SSC CGL, IBPS PO…)
  └─ Paper / Section → Topic            (topics reuse lessons, "Not clear", progress)
MockBlueprint: sections, question count per section, marks, negative marking, time limit, allowed types
```

### 3.2 Question types
- MCQ (single), MCQ (multiple), numeric answer (with tolerance), assertion–reason, match-the-following,
  **case study / passage** (one passage, several questions), **written / descriptive**.

### 3.3 Mock tests
- Built from a blueprint; **server-side timer** (start/end stored; auto-submit when time ends; resume after
  a dropped connection; refreshing the screen cannot restart the clock).
- Section switching, mark-for-review, question palette, calculator for numericals.
- Results: score with negative marking, **percentile vs everyone who took that mock**, section-wise time,
  accuracy per topic, weak topics → "study these lessons", attempt history graph.
- Fresh questions each mock (same rule as today's quizzes), from a verified question bank.

### 3.4 Written answers marked by AI
1. Student **types** the answer or **photographs** handwritten pages (vision model reads the handwriting).
2. The AI marks against a **model answer + marking scheme** (points list, e.g. "correct section quoted –
   1 mark, computation – 2 marks"), gives **step-wise marks** and short feedback ("you missed the
   exemption under section …").
3. Safety: a confidence score; low-confidence answers go to a **human examiner queue** in the admin panel;
   students can "request re-check". Calibrate on 50–100 sample answers marked by a qualified person
   before launch.
4. Cost per written answer ≈ ₹1–4 (text) / ₹3–8 (photos) — include in pricing or give N per month.

### 3.5 Content quality for professional exams
- Topic list from each body's **official syllabus** (ICAI, ICMAI, TN TRB, TNPSC, SSC…) — their study
  material is copyrighted; we never copy it.
- **Versioned by attempt** (e.g. "CA Inter – May 2027"): tax and law topics change every Finance Act /
  notification; old versions are frozen, new ones reviewed.
- Every AI question still passes the independent answer check; for law/tax add a **subject-expert review
  queue** before questions are shown (admin panel: approve / edit / reject).
- Lessons: a "whiteboard / diagram" visual style for adults instead of the storybook style.

### 3.6 Effort (rough)

| Work | Time |
|---|---|
| Exam / paper / blueprint model, question types, admin editor | 1.5–2 weeks |
| Mock test player (timer, palette, review, resume), results + percentile | 2 weeks |
| Written answers: typing + photo, AI marking, examiner queue | 2–3 weeks |
| First exam content (e.g. CA Foundation or TET) incl. expert review | 2–4 weeks, mostly expert time |

---

## 4. Phase C — several apps from one codebase

- **Mobile:** Expo app variants. `app.config.ts` reads `APP_VARIANT` (`school` / `exams`) and sets app
  name, package (`com.edsolution.teacherassistant` / e.g. `com.edsolution.examprep`), icon, colours, URL
  scheme, API URL and Firebase file; `eas.json` gets a build profile per app. Screens unique to one app
  sit behind a feature flag from the server (`/config`).
- **Backend:** the same code deployed twice on the VPS (`/docker/personal-teacher-assistant`,
  `/docker/exam-prep`), each with its own database, `.env.prod`, Google client IDs, Play product IDs and
  domain (e.g. `api.teacherassistant.sbs`, `api.<exam-domain>`). Separate databases avoid mixing
  children's data with adult users and keep each app's backups/restores independent.
- **Shared accounts:** Google Cloud project, Brevo, OpenAI and Google TTS keys can be shared (separate
  keys per app is better for tracking cost); one Play developer account publishes both apps.

---

## 5. Running costs (estimates)

| Item | Now | With all classes + exams |
|---|---|---|
| AI lesson (first open per topic, language and style) | ₹25–45 | same; ~₹1–2 lakh if every school topic got a lesson in 2 languages |
| Media storage per lesson | 5–20 MB | 4,000+ topics × 2 languages ≈ 100–200 GB → move media to object storage (e.g. Cloudflare R2, about $1.5/month per 100 GB, free downloads) |
| Server | current KVM 2 (shared) | KVM 4/8 or a second VPS when daily users > ~1,000, or when video rendering queues up |
| Email codes | Brevo free (300/day) | Brevo paid (~$9–25/month) above ~300 sign-ins/day |
| Google Play fee | 15% of subscriptions | same |

---

## 6. Pricing ideas (to test, not fixed)
- School: ₹99/month · ₹999/year (current); junior (1–5) ₹49–79/month; single topic ₹75.
- Exam app: ₹299–499/month or ₹1,999–3,999 per attempt; mock-test packs; written-answer marking credits.
- Free tier: first topic of every subject / one free mock per exam.

---

## 7. Main risks
1. **AI accuracy** in senior science, maths and law/tax → fact-check, answer verification, expert review queue, "report a mistake" button.
2. **Children's data rules** (Families policy, DPDP) → parent-led accounts, consent flow, minimal data, legal review.
3. **Scope** — doing everything at once delays everything → strict phase order, each phase launched before the next starts.
4. **Content volume** — syllabus files need your PDFs and a teacher's check, especially Tamil.
5. **Server load** — video rendering is heavy → monitor; move media to object storage early.

---

## 8. Milestones

| # | Milestone | Depends on |
|---|---|---|
| M0 | 10th TN live on Google Play (closed test 12×14 days, payments on) | Play identity verification |
| M1 | Course level + 9th / 11th / 12th TN | M0, PDFs |
| M2 | Parental consent flow (DPDP) | M1 |
| M3 | CBSE 6–12 | M1, CBSE/NCERT syllabus |
| M4 | Classes 1–8 with parent-led accounts + child-safe screens; Families policy review | M2 |
| M5 | Exam engine (mock tests, written answers, examiner queue) | M1 |
| M6 | Exam app variant + first exam (CA Foundation or TET) published | M5, expert reviewer |

## 9. Decisions needed from you
1. After 10th: which comes first — **TN 9/11/12** or **CBSE**?
2. Classes 1–8: start with **parent-led accounts** as proposed?
3. First professional/competitive exam to build (CA Foundation, CMA, TET, TNPSC Group 4…), and do you
   have a **qualified reviewer** (CA / teacher) for its questions and written-answer marking?
4. Exam app name + domain (e.g. a second `.in`/`.sbs` domain).
5. Budget ceiling per month for AI + server, so we can set spending alerts.
