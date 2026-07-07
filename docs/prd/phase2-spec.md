# Spec: Phase 2 — Customers + Sessions + Participants

**Status:** Ready to implement
**Created:** 2026-07-07
**Parent PRD:** `engage2win-app-enhancements.md` (Phase 2 of 5)
**Builds on:** Phase 1 (auth + SQLite). No new libraries; no Node.

## Goal

Let a facilitator create customers, create sessions under them (objectives +
participants), and manage a session workspace — all scoped by ownership
(facilitator sees own; admin sees all).

## Non-goals

Agenda builder (Phase 3); map mechanics + in-session upload (Phase 4); per-map-type
scoring (Phase 5); Alembic migrations (`create_all` adds the new tables).

## Navigation decision

- `/` becomes the **workspace dashboard** (`home.html`): the user's customers +
  prominent CTAs ("Analyze a map", "New customer").
- The standalone analyzer **form** moves to `GET /analyze/new` (`index.html`); the
  worker endpoint `POST /analyze` is unchanged.
- Phase 4 later folds map upload into the session workspace; the standalone quick
  analyzer stays available.

## Data model (SQLAlchemy / SQLite)

| Entity | Fields |
|--------|--------|
| **Customer** | id · owner_user_id→User · name (req) · industry · notes · created_at |
| **Session** | id · customer_id→Customer · owner_user_id→User · title (req) · objectives (text) · language (en\|es\|ca) · scheduled_date (date, nullable) · status (planned\|running\|complete, default planned) · created_at |
| **Participant** | id · session_id→Session · name (req) · role_dept · email (nullable) |

- `db.create_all()` creates the three new tables on startup (existing tables untouched).
- Cascade: deleting a Customer deletes its Sessions; deleting a Session deletes its
  Participants (`cascade="all, delete-orphan"`).

## Ownership

- Helper `owned(model)` → `model.query` filtered by `owner_user_id == current_user.id`,
  or unfiltered if `current_user.is_admin`.
- Cross-user access returns **404** (not 403) to avoid leaking existence — matches the
  Phase 1 job-scoping convention.

## Routes (all `@login_required`, ownership-checked)

| Method | Path | Behavior |
|--------|------|----------|
| GET | / | dashboard (customers + CTAs) |
| GET | /analyze/new | standalone analyzer form (was `/`) |
| GET/POST | /customers | list / create customer |
| GET | /customers/<id> | customer detail + its sessions |
| POST | /customers/<id>/edit | edit customer |
| POST | /customers/<id>/sessions | create a session under the customer |
| GET | /sessions/<id> | session workspace |
| POST | /sessions/<id>/edit | edit title/objectives/status/date/language |
| POST | /sessions/<id>/participants | add participant |
| POST | /sessions/<id>/participants/<pid>/delete | remove participant |

## Error cases

- Empty customer name / session title / participant name → 400 (re-render w/ message).
- Access a customer/session not owned (and not admin) → 404.
- Unauthenticated → 302 /login (pages); consistent with Phase 1.

## Files

**Change:** `app/models.py` (+3 models, ownership helper), `app/server.py` (dashboard at
`/`, analyzer form → `/analyze/new`, register blueprint, import Customer/Session),
`app/templates/base.html` (nav), `app/templates/result.html` ("Analyze another" →
`/analyze/new`), `app/tests/test_server.py` (index test → `/analyze/new`).

**Create:** `app/workspace.py` (blueprint), `app/templates/home.html`, `customers.html`,
`customer_detail.html`, `session.html`, `app/tests/test_workspace.py`.

## Tests (temp DB; per-test reset)

- Create customer → in list; second user does NOT see it; admin sees all.
- Create session under a customer; workspace renders objectives + participants.
- Add participant → shown; remove → gone.
- Edit session status planned→running→complete persists.
- Ownership: user B → 404 on user A's customer and session.
- Empty-name validations → 400.
- Dashboard `/` renders; `/analyze/new` renders the upload form.
- Existing 37 tests still pass (index test updated).

## Build order

spec → models → workspace blueprint → home/routing rework in server.py → templates →
nav + result link → tests → run & verify → commit.
