# Followthrough

Project location: `/Users/CamThePanda/Desktop/projects/python/followthrough`. Open this folder in PyCharm. Existing interpreter: `backend/.venv/bin/python`.

A personal, local trading journal focused on execution and plan adherence. Django 5.2, React 19 with Vite, and SQLite. Includes your 13 trading rules; no sample trading results are included.

## Run locally

Use Python 3.12+ and Node.js 22.12+ (Node 24 works too). Your Mac's default Python 3.8 and Node 18 are too old for this stack. The initial setup in this folder already has dependencies installed. The app uses two terminals.

Backend, from the project root:

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_rules
python manage.py runserver localhost:8000
```

For later starts, only activate the existing environment and run `python manage.py runserver localhost:8000`. `seed_rules` skips an existing rulebook.

Frontend, in another terminal from the project root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/` to Django. Save persists the plan, assessments, added trades, and reflection to SQLite. Add trade adds a row to your current draft; it autosaves with the day, or click Save to persist it immediately. Rulebook changes save immediately. Stop each server with Ctrl+C.

## PyCharm and VS Code

- Open `backend` in PyCharm. Select the existing `backend/.venv/bin/python` interpreter. Create a Python run configuration for `manage.py` with arguments `runserver localhost:8000` and working directory `backend`. This does not require PyCharm's Django-specific integration.
- Open `frontend` in VS Code. Use a terminal with Node 22.12+ or Node 24 active, then run `npm run dev`.
- Alternatively, open this entire project in either editor. Source is separated into `backend/apps/journal` for business logic and `frontend/src` for the UI.

## Daily workflow

1. Pick a date and write your morning plan, including five tickers and your top three opportunities.
2. Log each completed trade's symbol, direction, net P&L after fees, and notes. Use one consistent account currency.
3. Assess all 13 rules as Followed, Broken, or Not applicable. Every-trade rules mean all trades must comply for a Followed assessment. A no-trade day can use Not applicable for rules that did not apply.
4. Write a reflection and save the day. Reopen saved days from Calendar.

The Discord rule is a self-assessment. This app does not send Discord messages or automatically validate broker activity. Trade ideas can span multiple fills; the three-idea limit is also self-assessed.

## Grading

Your initial rules all have weight 1. You can edit importance from 1–10 in Rulebook. Score = followed weights / applicable weights × 100, rounded to the nearest whole percent (half rounds up). N/A rules are excluded. A pending assessment, an empty checklist, or an entirely N/A checklist leaves the grade pending.

A: 90–100, B: 80–89, C: 70–79, D: 60–69, F: 0–59. With all 13 applicable, 12 followed = 92% (A), 11 = 85% (B), 10 = 77% (C). There are no automatic-fail rules in this version. P&L never affects the grade.

Saved days retain their original rule text and weights. Editing the rulebook affects new, unsaved days only. Saving a day again updates it rather than creating a duplicate. Grades are recomputed by Django from server-owned rule weights.

## Data and scope

- Database: `backend/db.sqlite3`. Stop the backend before copying this file for a backup; keep backups outside the project if you plan to remove it.
- Personal, single-user localhost application. It has CSRF checks but no login and development settings; keep both servers bound to loopback. Hosting or multi-user use would need authentication and production configuration.
- This is an initial working journal, not a complete TradeZella replacement. Broker import, per-trade rule assessments, entry/exit calculations, and automated limits are not implemented.

## Verification

```sh
cd backend
.venv/bin/python manage.py test apps.journal
.venv/bin/python manage.py check
```

```sh
cd frontend
npm run build
```

Tests cover weighted grading, N/A and pending handling, historical rule snapshots, P&L independence, invalid submissions, and CSRF enforcement. Browser verification checks loading, assessments, and saving/history.

## API

- `GET /api/state/`: rulebook, saved days, and CSRF token.
- `POST /api/rules/`: add a rule; pass an existing `id` to replace it for future days.
- `PUT /api/days/YYYY-MM-DD/`: save or update a day.

Writes require the CSRF cookie and `X-CSRFToken` header. The frontend gets both through the state request. React's score is a live preview; Django is authoritative when saving.

## Calendar and appearance

The Calendar tab shows each saved daily execution grade. A uses green, B yellow, C orange, and D/F red, with 60% alpha on the cell background and fully opaque text. Click any date to open its daily review. Pending and unlogged days stay neutral.

Average timeframe supports the displayed month, trailing 7 or 30 calendar days including today, or a custom inclusive date range. Each graded day counts equally; pending and missing days are excluded. The mean of saved numeric daily scores is rounded to a whole percent and mapped to the same A–F thresholds. Month navigation changes the month-based average; rolling and custom ranges remain independent of the displayed month.

Use the Dark mode / Light mode button beneath navigation to change appearance. The preference is stored in this browser's local storage; journal data remains in SQLite.

Calendar logic checks: from `frontend`, run `node --test src/calendar.test.js`.


## Automatic saving

Daily journal edits save after 3 seconds without changes, with a 30-second fallback while editing continuously. Only the edited day's record is sent; unchanged days are not written. The Save button writes the currently open day immediately. Date switching waits for pending changes to save, and stays on the current day if saving fails.

Plans, assessments, reflections, added/removed trades, and unfinished trade-entry drafts are saved. Draft trades do not affect P&L until added. Rulebook changes are global and still use Save rule. Successful saves show a friendly confirmation near the top that fades and disappears after 5 seconds; failures remain visible and changes stay in memory for retry. Closing before a save completes still triggers the browser's unsaved-change warning.

Run `python manage.py migrate` when updating an older installation to add the trade-draft field.


## Project structure

The Django layout follows a configuration/apps/services structure inside `backend`, while React stays in `frontend`. The project name remains Followthrough; `config` describes Django's configuration package, and `journal` remains the app's database identity.

```text
followthrough/
├── .github/workflows/ci.yml
├── pyproject.toml
├── Dockerfile
├── README.md
├── backend/
│   ├── manage.py
│   ├── config/
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   └── settings/
│   │       ├── base.py
│   │       ├── local.py
│   │       └── production.py
│   ├── apps/
│   │   ├── core/validation.py
│   │   └── journal/
│   │       ├── apps.py
│   │       ├── models.py
│   │       ├── services.py
│   │       ├── selectors.py
│   │       ├── serializers.py
│   │       ├── grading.py
│   │       ├── views.py
│   │       ├── urls.py
│   │       ├── migrations/
│   │       ├── management/commands/
│   │       └── tests/
│   ├── static/
│   ├── templates/
│   ├── db.sqlite3
│   ├── media/
│   └── .venv/
└── frontend/
```

`services.py` validates and writes records; `selectors.py` reads data; `serializers.py` shapes API responses; `grading.py` calculates execution grades. Views handle HTTP input/output. Models and migration labels are preserved so existing SQLite tables and uploaded files continue to work. `core` contains shared validation; no unused users/authentication app was added.

Dependencies are declared in the root `pyproject.toml`. From the project root, install with `backend/.venv/bin/python -m pip install -e .`. The legacy requirements command remains available when run from `backend`. This is a standard Python package configuration compatible with pip or uv; no uv/Poetry lockfile is claimed or required.

PyCharm still uses `backend/.venv/bin/python`, `backend/manage.py`, and `backend` as the working directory. The default settings module for manage.py is now `config.settings.local`. Update any custom IDE environment variable previously set to `followthrough.settings`.

Local startup commands are unchanged. WSGI/ASGI default to `config.settings.production`, which requires `DJANGO_SECRET_KEY` (50+ characters) and comma-separated `DJANGO_ALLOWED_HOSTS`. Optional `DJANGO_CSRF_TRUSTED_ORIGINS` contains comma-separated HTTPS origins. Production settings enforce HTTPS and secure cookies. These settings are configuration groundwork; the personal app still has no user authentication and must not be exposed publicly without adding it.

The Dockerfile builds a backend-only Gunicorn image, not a complete hosted React application. A future deployment needs persistent storage for SQLite/media, migrations, HTTPS termination and frontend serving. It is not started by this refactor. GitHub Actions runs backend checks/tests and the frontend build/tests when this repository is pushed to GitHub; nothing has been pushed or deployed.

Attachment backups must include both `backend/db.sqlite3` and `backend/media/`.


## Review status and date selection

The daily header shows Reviewed once every rule has been assessed (Followed, Broken, or Not applicable). An empty checklist or a pending rule shows Not reviewed. This indicates completeness, not the execution grade. The themed date picker opens a day immediately after pending changes have saved, replacing the old Open date button. Its selected date has a green circular highlight in both themes.


## Trade entry modes

Manual, CSV import, and the future Broker sync mode share one session trade list. CSV imports append to the open day and autosave. Required headers: symbol (or ticker), side (or direction; Long/Short), pnl (or net pnl). Optional notes and date columns are supported; dates must match the active day in YYYY-MM-DD format. P&L uses plain decimal numbers with up to two decimal places, without currency symbols or thousands separators. Files are limited to 2 MB and 500 trades per day. A validated preview requires Add trades before anything is appended. Re-importing can create duplicates; no broker-specific deduplication is implemented. Broker sync is a placeholder only.

Calendar replaces the removed History page. Dates and timeframe options open in anchored popovers. Photo/deletion modals lock background scrolling and restore it when closed.
