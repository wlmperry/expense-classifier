# Development

**There is no application code in this repository yet.** Setup today is: clone it and read the docs. Install, run, migration, and test commands will be documented here as each one actually lands. This file records what is established, not what is assumed.

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

**PostgreSQL** may run on the Windows host or inside WSL, depending on the developer's environment. The team has not yet standardized a single local database setup. When setup instructions are added, document the supported configurations and the connection details each one requires rather than assuming every developer runs PostgreSQL in the same place.

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

## Not established yet

These will be documented here once implementation work settles them:

- configuration variable names, ports, and database names
- JavaScript package-management conventions
- frontend testing and linting tooling
- PostgreSQL driver and connection configuration
