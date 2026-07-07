# Spec: Phase 1 — Auth + SQLite Data Layer

**Status:** Ready to implement
**Created:** 2026-07-01
**Parent PRD:** `engage2win-app-enhancements.md` (Phase 1 of 5)
**Scope:** Foundation only — auth, roles, DB layer; gate the existing analyzer behind login.

---

## Goal

Add login + roles + a SQLite/SQLAlchemy foundation to the existing Flask app (`app/`),
and require a logged-in user for the current upload→analyze flow. The `claude` CLI
analysis core is unchanged. No Node.

## Non-goals

Customers/sessions/agenda/maps UI; per-map-type scoring; Alembic migrations
(`create_all` for MVP); email verification / password reset; CSRF tokens (deferred).

## Account model (decided)

- **First registration** (no users exist yet) → that user is created as **admin**, open.
- **After that**, registration requires a valid, unused **invite code**.
- **Admins** create invites (optionally pre-setting email + role). Invites are single-use.

## Data model (SQLAlchemy / SQLite)

| Entity | Fields |
|--------|--------|
| **User** | id pk · email (unique, required) · password_hash · name · role `facilitator`\|`admin` (default facilitator) · created_at |
| **Invite** | id pk · code (unique, random) · email (optional) · role (default facilitator) · created_by → User · used_by → User (nullable) · created_at · used_at (nullable) |

- DB file: `app/engage2win.db` (gitignored). `db.create_all()` on startup.
- Password hashing: werkzeug `generate_password_hash` (scrypt) / `check_password_hash`.

## Files

**Create**
- `app/models.py` — `db = SQLAlchemy()`, `User(UserMixin)`, `Invite`.
- `app/auth.py` — Blueprint: `GET/POST /register`, `GET/POST /login`, `POST /logout`,
  admin-only `GET/POST /invites` (create + list).
- `app/templates/login.html`, `register.html`, `invites.html` — branded.
- `app/seed.py` — `python -m app.seed <email> <password>` to create an admin out-of-band.
- `app/tests/test_auth.py` — auth + invite tests (temp DB).

**Change**
- `app/server.py` — init `db` + `LoginManager` + `SECRET_KEY`; register auth blueprint;
  `@login_required` on `/`, `/analyze`, `/status`, `/result`, `/uploads`; scope the job
  store to `current_user.id`; unauthorized handler → **401 JSON** for XHR/API
  (`/analyze`, `/status`), **302 redirect** for pages; `db.create_all()` at startup.
- `app/templates/base.html` — show logged-in user + logout; admin sees an "Invites" link.
- `app/requirements.txt` — add `Flask-Login`, `Flask-SQLAlchemy`.
- `.gitignore` — `app/*.db`.
- `.env.example` — `SECRET_KEY`.

## Routes

| Method | Path | Auth | Behavior |
|--------|------|------|----------|
| GET/POST | /register | public | first user→admin; else require invite code |
| GET/POST | /login | public | set session |
| POST | /logout | login | clear session |
| GET/POST | /invites | admin | create/list single-use invite codes |
| GET | / , /result/<id> , /uploads/<f> | login | existing pages, now gated |
| POST | /analyze , GET /status/<id> | login | existing API, JSON-401 if unauthenticated |

## Error cases

- Not logged in → page: 302 to /login · API: 401 JSON.
- Duplicate email → 400. · Bad credentials → 401. · Weak/empty password → 400.
- Register without/with invalid invite (when users exist) → 400.
- Non-admin hitting /invites → 403.

## Tests (temp SQLite; CLI mocked where needed)

- First registration creates an **admin**; password stored hashed (never plaintext).
- Second registration without a code → rejected; with a valid code → succeeds (facilitator).
- Invite is single-use (second use rejected).
- Login sets session; bad password → 401; logout clears session.
- Unauthenticated GET / → 302 login; unauthenticated POST /analyze → 401 JSON.
- Authenticated flow reaches the analyzer; role defaults to facilitator.
- Non-admin GET /invites → 403.
- `seed.py` creates an admin.
- Existing 27 tests still pass.

## Security notes

- `SECRET_KEY` from `.env.local` (gitignored); dev fallback logs a warning.
- No CSRF tokens yet (Flask-WTF deferred) — acceptable for a local single-user tool; noted.
- Data-ownership enforcement (`owner_user_id` filtering) becomes meaningful in Phase 2 when
  Customers/Sessions exist; Phase 1 establishes `current_user`, roles, and the DB plumbing.

## Build order

requirements → models → auth blueprint (+ invite) → wire server.py → templates → seed →
tests → run & verify.
