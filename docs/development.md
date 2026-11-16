# Development

**The initial FastAPI backend foundation, a PostgreSQL/SQLAlchemy/Alembic persistence foundation, and a React/TypeScript/Vite frontend foundation have all been established.** See Backend setup, Database setup, and Frontend setup below for the install, run, and test commands that have been verified. This file records what is established, not what is assumed.

## Prerequisites

The planned stack requires the following tools or services as development progresses:

- **Git**
- **Python** -- backend, tests, and tooling
- **Node.js** -- runtime for frontend development tooling
- **PostgreSQL** -- application database

Specific versions are not pinned yet, except Node.js: the frontend has been verified against Node.js 24 (LTS) and npm 11.

## Choosing an environment

The team develops on both native **Windows** and **WSL2 / Ubuntu**. Both are supported.

For a given working copy, keep development commands and tooling within one execution environment. For example, a repository stored in WSL should generally use WSL Git, Python, Node.js, and PostgreSQL tooling rather than alternating between Windows and Linux versions against the same files.

An editor or GUI running on Windows may still work with a WSL repository; the important part is keeping the development toolchain consistent.

Whenever you write a command down -- in a document, an Issue, or a pull request -- say which environment it targets.

## Differences that actually matter

**Virtual environment activation** differs by shell. `.venv`, `venv/`, and `env/` are already ignored by `.gitignore`, so an environment created in the repository root will not be committed:

- Windows PowerShell -- `.venv\Scripts\Activate.ps1`
- WSL and Linux shells -- `source .venv/bin/activate`

**Shell and path syntax are not interchangeable.** PowerShell is not bash. Path separators, environment variable syntax, and quoting rules all differ, and a command copied across without adjustment will usually fail.

**Line endings** can churn diffs when the same files are edited from both environments. If you see a diff where every line changed but little appears different, line ending conversion is one possible cause.

**Repository location under WSL.** If you develop in WSL, keeping the clone inside the Linux filesystem -- under your home directory rather than on a mounted Windows drive -- is recommended, because file access across the mount boundary is noticeably slower. This is a recommendation, not a requirement.

**PostgreSQL** can run natively on Windows, inside WSL, or in a local Docker container -- Docker is optional and is not required by the project. See "Database setup" below for the local-development convention and how each developer configures their own credentials.

**Setting an environment variable for one command** differs by shell, which matters if you need to override `DATABASE_URL` without editing `.env`:

- Windows PowerShell -- `$env:DATABASE_URL = "..."`
- WSL and Linux shells -- `DATABASE_URL="..." <command>` or `export DATABASE_URL="..."`

## Secrets and local configuration

Never commit secrets, credentials, `.env` contents, or real financial data. `.env` is already ignored by `.gitignore`. This repository is public -- treat anything committed to it as published.

## Backend setup (Python / FastAPI)

From the repository root:

```
python -m venv .venv
```

Activate it:
- Windows PowerShell -- `.venv\Scripts\Activate.ps1`
- Git Bash -- `source .venv/Scripts/activate`
- WSL / Linux -- `source .venv/bin/activate`

Install dependencies:

```
pip install -r requirements.txt
```

Run the development server:

```
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`.

Run tests:

```
python -m pytest
```

Run the linter:

```
ruff check .
```

## Frontend setup (React / TypeScript / Vite)

From the `frontend/` directory:

```
npm install
```

Copy the API configuration boundary and adjust it if the backend runs somewhere other than `http://127.0.0.1:8000`:

```
cp .env.example .env
```

Run the development server:

```
npm run dev
```

Run a production build:

```
npm run build
```

Run tests:

```
npm run test
```

Run the linter:

```
npm run lint
```

## Cross-origin requests in local development

The browser and the API run on different origins in local development -- the Vite dev server on `http://localhost:5173`, the backend on `http://127.0.0.1:8000` -- so the backend must explicitly allow the frontend's origin. A plain `GET` with no custom headers would be a CORS "simple request": the browser sends it directly and only blocks the frontend JavaScript from reading the response if the CORS header is missing. But every request a logged-in frontend sends carries an `Authorization: Bearer ...` header with the session token (`app/auth.py`, Issue #44), and `Authorization` is not one of the browser's CORS-safelisted headers -- so even `GET /expenses` triggers an `OPTIONS` "preflight" request first, same as `POST`/`PATCH`/`DELETE`; if the preflight is not allowed, the browser never sends the real request at all.

`app/main.py` configures `CORSMiddleware` to allow `http://localhost:5173` (Vite's default dev address) plus the deployed frontend's origin (Issue #42), and `GET`, `POST`, `PATCH`, and `DELETE` requests, matching what the frontend currently needs. `allow_headers` explicitly lists `Authorization`, since it is not CORS-safelisted and preflight requests would otherwise be rejected, and `Content-Type` -- listed for clarity even though Starlette's `CORSMiddleware` always allows its own CORS-safelisted request headers (`Accept`, `Accept-Language`, `Content-Language`, and `Content-Type`) regardless of `allow_headers`. If the frontend dev server ever runs on a different port or host, or a future Issue needs another HTTP method or a non-safelisted header from the browser, update the allowed origin/methods/headers there rather than widening it speculatively ahead of need.

## Database setup (PostgreSQL / SQLAlchemy / Alembic)

This establishes PostgreSQL persistence, including the `expenses` table (Issue #12). Most of `python -m pytest` does not require a database connection; the persistence tests in `tests/test_expense_model.py` do, against the dedicated test database described in "Running persistence tests" below, and skip cleanly with a clear message if it is not configured.

1. Have a running local PostgreSQL server with a database and role the application can use.

   - PostgreSQL may be installed natively on Windows, installed/run inside WSL, or run in a local Docker container if preferred. Docker is optional and is not required by the project.
   - Each developer uses their own local PostgreSQL instance and their own credentials. Never share `.env` files or database passwords between developers.
   - The documented local-development convention is a database named `expense_classifier_dev` and a role named `expense_classifier`. Each developer chooses their own local password and stores it only in their own gitignored `.env`.
   - This workflow was verified against PostgreSQL 18 running inside WSL2/Ubuntu and independently against a temporary PostgreSQL 18 instance on Windows during PR review.
   - **Native Windows setup:** after installing PostgreSQL and confirming the service is running, create the `expense_classifier` role and `expense_classifier_dev` database locally, then continue with step 2 below to configure your `.env`.

2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your connection string:

   ```
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
   ```

   `.env` is gitignored and must never be committed.
3. Install dependencies (`pip install -r requirements.txt`) -- this pulls in SQLAlchemy, Alembic, and the `psycopg` (v3) PostgreSQL driver.
4. Verify SQLAlchemy can actually connect and query the database:

   ```
   python -c "from sqlalchemy import text; from app.database import engine; conn = engine.connect(); print(conn.execute(text('SELECT 1')).scalar()); conn.close()"
   ```

   This should print `1`. Constructing the engine alone does not prove connectivity -- this runs a real query.
5. Verify Alembic is wired to the same configuration and can reach the database:

   ```
   alembic current
   alembic upgrade head
   ```

   This reads `DATABASE_URL` through `app/database.py` (see `alembic/env.py`) rather than a hard-coded connection string in `alembic.ini`. On a fresh database, `alembic current` reports no revision until `alembic upgrade head` is run; that upgrade applies the initial migration (Issue #12), creating the `expenses` table alongside Alembic's own `alembic_version` tracking table.

6. Create the dedicated test database used by persistence tests. It is separate from `expense_classifier_dev` so automated tests never depend on or modify your normal development data. Creating a database typically requires your PostgreSQL admin/superuser access, since the `expense_classifier` role itself does not need `CREATEDB`. On WSL2/Ubuntu, this was verified with:

   ```
   sudo -u postgres createdb --owner=expense_classifier expense_classifier_test
   ```

   A differently configured PostgreSQL installation (for example, native Windows, or a different local admin role) may need an equivalent admin command instead.

   Then add `TEST_DATABASE_URL` to your `.env`, using the same role/credentials as `DATABASE_URL` but pointing at `expense_classifier_test`:

   ```
   TEST_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/expense_classifier_test
   ```

## User accounts and the demo account

Every expense belongs to a user, so you need an account to use the app (Issue #44). With the backend and frontend running, open the frontend and choose **Create an account** on the login screen. See "Established API decisions" in `docs/architecture.md` for how accounts and sessions work.

The migration that added accounts (`8c5fbee890de`) moved every expense that already existed into a `demo@example.com` account, with a password nobody knows. To use that account, give it a password with `scripts/set_password.py`. From the repository root, with the virtual environment active:

```
python -m scripts.set_password
```

It asks for the email and the new password (twice). The password is read with `getpass`, so it is never shown, put on the command line, or saved in shell history; run it in a real terminal, since the hidden prompt needs a keyboard. It works for any existing account, uses the same password rules as sign-up, and ends the account's existing sessions.

The script changes whichever database `DATABASE_URL` points at -- your local `expense_classifier_dev` by default. To set a password on the deployed database instead, set `DATABASE_URL` for that terminal session only (see "Setting an environment variable for one command" above) rather than editing `.env`, and never paste the connection string into chat or commit it.

## The ML classifier and its training data

New expenses are categorized by keyword rules first, then by a scikit-learn model when no rule matches (Issue #55; see "Machine-learned categorization" in `docs/architecture.md`). The model trains from `app/training_data.csv` each time the backend starts, so there is no model file to build or download.

To see how well it does on examples it has not trained on, from the repository root with the virtual environment active:

```
python -m scripts.evaluate_classifier
```

It prints overall accuracy, precision and recall per category, and how the confidence threshold (`MIN_MODEL_CONFIDENCE` in `app/categorize.py`) trades how often the model answers against how often it is right.

To improve the model, add rows to `app/training_data.csv` (`merchant,description,category`, using one of the 20 category names exactly), then rerun the script. Rows with descriptive words real bank lines contain ("petro", "pizzeria", "rx") help more than extra brand names, since they carry over to merchants the model has never seen. Keep every row made up: no real transactions or account data. `tests/test_ml_classifier.py` fails if held-out accuracy drops below 45% or any category has fewer than 15 examples.

## Running persistence tests

Persistence tests (`tests/test_expense_model.py`) run against the dedicated `expense_classifier_test` database created in step 6 above -- never against `expense_classifier_dev`. At the start of a test session they drop and recreate the ORM-mapped schema there (`Base.metadata.drop_all()` / `create_all()`), and each individual test runs inside a transaction that is rolled back afterward, so no test data persists between tests or between runs.

If `TEST_DATABASE_URL` is not set, persistence tests are skipped with a clear message rather than silently falling back to `DATABASE_URL` -- `python -m pytest` still runs cleanly, just without exercising persistence.

## Continuous integration

CI (`.github/workflows/ci.yml`) runs the same commands described above -- `ruff check .` and `python -m pytest -rs` for the backend, `npm ci`, `npm run lint`, `npm run test`, and `npm run build` in `frontend/` -- on Ubuntu with Python 3.13 and Node.js 24. The backend job starts its own PostgreSQL 18 container with an `expense_classifier_test` database, so persistence tests run there instead of being skipped. If CI fails, running the same command locally should reproduce it.

## Not established yet

Backend, persistence, and frontend foundations are all established as of this writing. This section records the next gap once one appears.
