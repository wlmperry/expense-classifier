# Development

**The initial FastAPI backend foundation has been established, and a PostgreSQL/SQLAlchemy/Alembic persistence foundation now exists; frontend application code has not yet been added.** See Backend setup and Database setup below for the install, run, and test commands that have been verified. This file records what is established, not what is assumed.

## Prerequisites

The planned stack requires the following tools or services as development progresses:

- **Git**
- **Python** -- backend, tests, and tooling
- **Node.js** -- runtime for frontend development tooling
- **PostgreSQL** -- application database

Specific versions are not pinned yet; they will be recorded here once the first backend and frontend code establishes them.

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

**PostgreSQL** may run on the Windows host or inside WSL, depending on the developer's environment. The team has not yet standardized a single local database setup; the steps below have been verified against a PostgreSQL 18 server running inside WSL2/Ubuntu. If you run PostgreSQL elsewhere (Windows host, another WSL distro, or another local instance), the same `DATABASE_URL` configuration mechanism applies, but the connection details and server installation/startup commands may differ.

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

## Database setup (PostgreSQL / SQLAlchemy / Alembic)

This establishes the persistence foundation only -- there is no Expense table or model yet. `python -m pytest` above does not require a database connection and stays independent of any local PostgreSQL setup.

1. Have a running local PostgreSQL server with a database and role the application can use. These steps were verified against PostgreSQL 18 running inside WSL2/Ubuntu, using an `expense_classifier_dev` database and an `expense_classifier` role as the documented local-development convention. Other local setups can use different names, hosts, and credentials -- only `DATABASE_URL` needs to point at them.
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

   This reads `DATABASE_URL` through `app/database.py` (see `alembic/env.py`) rather than a hard-coded connection string in `alembic.ini`. At this baseline, with no migration revisions written yet, `alembic current` reports no application revision -- that is expected, not an error. Running `alembic upgrade head` against a fresh database at this baseline creates Alembic's own empty `alembic_version` tracking table (used to record which revision has been applied) but makes no application schema changes; it is a real database write, not a pure no-op.

Alembic is initialized with an `alembic/versions/` directory that contains no migration revision files yet. The first application/schema migration (the Expense table) belongs to Issue #12, not this persistence bootstrap.

## Not established yet

These will be documented here once implementation work settles them:

- JavaScript package-management conventions
- frontend testing and linting tooling
