# PRD: Engage2Win — Session-Based Facilitation Platform

**Status:** Approved (2026-07-01)
**Created:** 2026-07-01
**Owner:** Pablo Quintano
**Supersedes scope of:** Phase 1 Lean MVP (single-shot map analyzer in `app/`)

---

## Executive Summary

Evolve the engage2win app from a single-shot map analyzer into a **session-based
facilitation platform**. A logged-in facilitator sets up a **customer**, creates an
**engage2win session** (objectives + participants + agenda), is guided through the
**mechanics of each map type**, and uploads maps **during the session** so the existing
AI analysis runs **in the context** of that customer, session, and map type.

## Problem Statement

Today the app analyzes one map at a time with no memory, no user accounts, and no notion
of the session it belongs to. Facilitators run structured engage2win sessions (multiple
map types, an agenda, specific objectives, a specific customer), so an isolated map
evaluation misses the surrounding context that makes feedback trustworthy and useful.
There is also no way to save work, know who created it, or reuse a prepared agenda.

## Mission

Give facilitators one place to **plan, run, and evaluate** an engage2win session — where
every map analysis is grounded in the session's customer, objectives, and map type.

## Target Users

| User Type | Description | Primary Need |
|-----------|-------------|--------------|
| Facilitator (SC) | Runs engage2win sessions with a customer | Plan a session, guide activities, get context-aware map feedback |
| Participant | Customer-side attendee in the session | (Indirect) their maps evaluated meaningfully; may be listed, not a login user in v1 |
| Manager / Admin | Oversees facilitators | (Later) visibility across sessions; user management |

> Open question: do participants log in, or are they just records the facilitator manages? (Assumed: records only in v1.)

---

## Chosen Architecture (decided)

- **Extend the existing local Flask app** (`app/`) — no rewrite.
- **Add authentication** (email + password, hashed) and **user rights/roles**.
- **Add a local database: SQLite** (via SQLAlchemy) for users, customers, sessions,
  participants, agenda items, and stored map analyses.
- **Keep the `claude` CLI backend** (`validate/run.py`) as the vision core; extend the
  analysis context (customer + objectives + map type + mechanics).
- Local, single-machine, single-facilitator-per-machine by design (matches the earlier
  local-only decision). Multi-user hosting / Vercel remains a later phase.

---

## MVP Scope

### In Scope
- **Auth & roles:** register/login/logout; passwords hashed. Two roles: **facilitator**
  (sees only their own data) and **admin** (manages users, sees all sessions).
- **Customers:** create/list/edit a customer (name, industry, notes).
- **Sessions:** create a session under a customer with objectives, language, date, and a
  list of participants (name, role/dept).
- **Agenda builder:** add ordered agenda items (start time, duration, activity, map type),
  driven by the facilitator's existing **agenda skill/artifact** (to be integrated).
- **Map mechanics guidance:** for each of the 6 map types, a clear "how this map works"
  explanation shown before upload.
- **In-session map upload + analysis:** the current upload → RAG analysis, now attached to
  a session (and optionally an agenda item), with the session context fed into the prompt.
- **Per-map-type scoring:** each map type has its own tailored dimensions/criteria (not the
  shared 5), driven by a per-type prompt; still reported as Red/Amber/Green.
- **Persistence:** saved sessions, agendas, and past analyses are retrievable.

### Out of Scope (v1)
- Multi-user hosting, cloud deploy (Vercel), Supabase — deferred.
- Participant self-service logins.
- Real-time collaboration / multiple facilitators on one session.
- Anthropic API-key backend (stays on the `claude` CLI).
- Exporting a full session report as PDF (copy/print per map stays; agenda PDF export IS
  in scope via the ported builder; a combined session+maps report is later).
- Fine-grained permissions beyond the two facilitator/admin roles.

---

## Epics & User Stories

### Epic A — Accounts, customers & session planning

- **R1 — Login & user rights.**
  *As a* facilitator *I want to* register and log in *so that* my customers and sessions
  are private to me.
- **R2 — Define a customer.**
  *As a* logged-in facilitator *I want to* create the customer I'll run a session for
  *so that* all session work is organized under that customer.
- **R3 — Create a session.**
  *As a* facilitator *I want to* create a session with objectives and participants
  *so that* the session has a clear purpose and attendee list.
- **R4 — Build the agenda.**
  *As a* facilitator *I want to* define time slots and activities (using my agenda skill)
  *so that* I have a structured run-of-show for the engage2win process.

### Epic B — Map mechanics & in-session contextual analysis

- **R5 — Understand map mechanics.**
  *As a* facilitator *I want to* read the mechanics of each methodology map (Vision Keywords,
  Problem Statements, Metrics & Root-Cause, Capability Map, Criteria, Capability Ranking,
  Roadmap) *so that* I run each activity correctly. Content is sourced from the e2open
  playbook — see `reference/engage2win-methodology.md`.
- **R6 — Upload a map in-session.**
  *As a* facilitator *I want to* upload a map at the relevant point in the session
  *so that* the current AI analysis runs on it.
- **R7 — Context-aware analysis.**
  *As a* facilitator *I want* the analysis to consider the customer, session objectives,
  and map type *so that* the feedback is relevant to what we're actually working on.
- **R8 — Revisit past work.**
  *As a* facilitator *I want to* reopen a past session and its analyses *so that* I can
  review, continue, or correct them.

---

## Acceptance Criteria (v1)

- [ ] A visitor can register, log in, and log out; unauthenticated users are redirected to login.
- [ ] A user only ever sees customers/sessions they own.
- [ ] Passwords are stored hashed (never plaintext); no secrets in the repo.
- [ ] A facilitator can create a customer, then a session under it with objectives + ≥1 participant.
- [ ] A facilitator can add, reorder, edit, and remove agenda items (time, duration, activity, map type).
- [ ] Each of the 6 map types shows a mechanics explanation before the upload placeholder.
- [ ] Uploading a map inside a session runs the existing RAG analysis and saves the result to that session.
- [ ] The analysis prompt receives the session objectives + selected map type (verified in the request sent to the CLI).
- [ ] A saved session can be reopened later with its agenda and analyses intact.
- [ ] Existing 27 tests still pass; new features have happy + failure-path tests.

---

## Data Model (SQLite / SQLAlchemy)

| Entity | Key fields |
|--------|-----------|
| **User** | id, email (unique), password_hash, name, role (`facilitator`\|`admin`), created_at |
| **Customer** | id, owner_user_id → User, name, industry, notes, created_at |
| **Session** | id, customer_id → Customer, owner_user_id, title, objectives (text), language (`en`\|`es`\|`ca`), scheduled_date, status (`planned`\|`running`\|`complete`), created_at |
| **Participant** | id, session_id → Session, name, role_dept, email (optional) |
| **AgendaItem** | id, session_id → Session, position (int), type (`section`\|`break`\|`intro`), name, category, duration_min, description, activities (list), tips (list), roles, materials, output, map_type (nullable enum), enabled |
| **MapAnalysis** | id, session_id → Session, agenda_item_id (nullable), map_type, image_path, eval_json, description_md, band (`green`\|`amber`\|`red`), created_at |

- **MapType** is a fixed enum (not a table), aligned to the actual methodology maps
  (see `reference/engage2win-methodology.md`): `vision_keywords`, `problem_statements`,
  `metrics_root_cause`, `capability_map`, `criteria`, `capability_ranking`, `roadmap`.
  (The icebreaker "Map Clip" is not analysed.) Mechanics + per-type scoring signals live
  in config/content files derived from the playbook, not the DB.

---

## Technology Stack (this feature)

- Existing **Flask** app in `app/`.
- **SQLAlchemy + SQLite** for persistence (new).
- **Flask-Login** (or equivalent) for sessions/auth; **werkzeug** password hashing.
- Vision analysis unchanged: `validate/run.py` via the `claude` CLI.
- e2open brand styling already in `app/static/styles.css`.

## Security & Configuration

- Authentication required: **yes** (all app routes except register/login).
- Password hashing: yes (werkzeug `generate_password_hash`).
- New env vars: `SECRET_KEY` (Flask session signing) via `.env.local` (gitignored).
- Sensitive data: user credentials + customer/session content — local SQLite file, gitignored.
- Rate limiting: no (local single-user).

## API / Routes (high-level)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | /register, /login | Auth |
| POST | /logout | End session |
| GET/POST | /customers | List / create customers |
| GET/POST | /customers/<id>/sessions | List / create sessions |
| GET | /sessions/<id> | Session workspace (objectives, participants, agenda) |
| POST | /sessions/<id>/agenda | Add/reorder/edit agenda items |
| GET | /sessions/<id>/maps/<map_type> | Mechanics + upload placeholder |
| POST | /sessions/<id>/analyze | Upload + analyze in context (extends current /analyze) |
| GET | /sessions/<id>/result/<analysis_id> | Stored result (reuses current result page) |

> Full contract goes in `/plan:spec`. This is overview only.

## Success Metrics

- A facilitator can go from login → customer → session → agenda → first map analysis in one sitting without leaving the app.
- Context-aware analyses are judged more relevant than the context-free ones (facilitator spot-check).
- The >80% edit-not-redo bar from Phase 0 holds for in-session analyses.

## Implementation Phases

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| 1 | Auth + data layer (User, login, SQLite, ownership) | Log in; empty dashboard |
| 2 | Customers + Sessions + Participants | Create a customer and a session |
| 3 | Agenda builder (integrate the agenda skill/artifact) | Build a run-of-show |
| 4 | Map mechanics content + in-session upload wired to current analysis | Analyze a map inside a session |
| 5 | Context-aware prompt + stored/reopenable results | Session history with contextual feedback |

## Future Considerations

- Cloud/multi-user via the production stack (Next.js + Supabase + Vercel + API key).
- Full session report export (all maps + agenda) as PDF.
- Per-map-type scoring dimensions (see open questions).
- Manager/admin dashboards across facilitators.
- Participant logins / collaboration.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Scope creep (platform vs MVP) | High | High | Strict phasing; each phase demoable |
| Auth adds real security surface | Med | Med | Standard Flask-Login + hashing; local-only reduces exposure |
| Different map types may need different scoring | Med | Med | Decide per-map-type vs shared dimensions before Phase 5 (open question) |
| Agenda skill format unknown until shared | Med | Med | Integrate after reviewing the artifact (dependency) |
| Storing images/customer data locally | Low | Med | Keep DB + uploads gitignored; document location |

## Dependencies

- **Agenda skill/artifact** — RECEIVED: a React (TSX) single-file SPA (`agenda_builder.tsx`,
  Claude-Artifact style, persists via `window.storage`). Reusable assets: the engage2win
  **section library** (14 sections with category/activities/tips/roles/materials/output),
  the **category set** (which maps to the map types), the **setup fields** (customer,
  industry, day/hours, participants, roles, objectives, notes), and the **HTML/PDF export**.
  It already covers much of Epic A conceptually. Integration approach = Open Question 4.
- **Map mechanics content** — RECEIVED as source: the e2open Activities Playbook
  ("Activities & Training for Visioning Workshop e2open August25.pdf"), captured in
  `reference/engage2win-methodology.md` (7 maps: purpose, mechanics, expected output,
  evaluation signals). I draft the in-app content from this; facilitator validates.
- SQLAlchemy + Flask-Login added to `app/requirements.txt`.

## Resolved Decisions (2026-07-01)

1. **Map mechanics content:** MIX — facilitator provides source text for the map types
   they have; we draft the rest for review.
2. **Scoring:** PER-MAP-TYPE criteria — each map type gets its own dimensions tailored to
   what that map is for (not the shared 5). Requires per-type prompts + a flexible schema.
3. **Agenda artifact:** received as a React SPA (`docs/prd/reference/agenda_builder.tsx`).
4. **Agenda integration:** OPTION A — port to server-side Flask + vanilla JS, reusing the
   section library / categories / setup fields / PDF export; persist to SQLite. Keeps no-Node.
5. **User model:** FACILITATOR + ADMIN roles. Facilitators see only their own data; admin
   manages users and can see all sessions. Participants are records, not login users.
6. **Map ↔ agenda link:** FLEXIBLE — a map can attach to an agenda item (map type auto-set
   from its category) OR be uploaded ad-hoc in the session with a manually chosen map type.
   (`MapAnalysis.agenda_item_id` stays nullable.)

## Methodology basis (added 2026-07-01)

The maps, their mechanics, and what "good" looks like are now grounded in the e2open
Activities Playbook — see **`reference/engage2win-methodology.md`**. The seven analysable
maps and their evaluation signals are defined there; per-map-type RAG dimensions derive
directly from each map's "evaluation signals".

## v1 Map Scope (decided 2026-07-01)

v1 covers the **Day-1 trio** — `vision_keywords`, `problem_statements`,
`metrics_root_cause` — with full mechanics + per-map-type RAG scoring for each. The other
four maps (`capability_map`, `criteria`, `capability_ranking`, `roadmap`) are defined in
the methodology reference and added in a later phase. The `map_type` enum still includes
all seven; only the in-app mechanics/scoring content is limited to the trio for v1.

## Open Questions (remaining)

- Sign-off on the drafted per-map-type RAG dimensions for the trio (produced from the
  methodology "evaluation signals") — review at Phase 5.
- Agenda section library: align section→map_type mappings for the trio (and add a Roadmap
  activity when those maps come in a later phase).

## Appendix

- Related: `app/README.md`, `CLAUDE.md`, `validate/schema.json`
- Prior work: Phase 0 harness (`validate/`), Phase 1 MVP (`app/`)
