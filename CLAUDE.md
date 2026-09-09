# CLAUDE.md

## Project

Expense Classifier is a three-person undergraduate CS senior capstone: a full-stack application that records expenses and presents spending summaries, with machine-learning-assisted expense categorization planned after the basic expense pipeline works. It doubles as practice in collaborative Git/GitHub work, lightweight Agile delivery, and agentic AI-assisted development. See `README.md` for the human-facing overview.

## Current objective

The active milestone is the **first walking skeleton**, not the MVP -- proof that the layers can talk end to end:

React + TypeScript -> FastAPI -> SQLAlchemy -> PostgreSQL -> FastAPI -> React

A minimal expense should be accepted, validated, persisted, retrieved, and displayed. Do not introduce ML, OCR, authentication, advanced analytics, forecasting, or elaborate dashboards unless an assigned Issue calls for them. Once this milestone is met, this section is stale -- say so rather than working from it.

## Hard rules

- Never commit secrets, credentials, `.env` contents, or real financial data.
- The current Issue, repository documentation, and accepted project decisions outrank assumptions carried in from earlier AI conversations. Surface conflicts; do not resolve them silently.
- Keep changes scoped to the assigned Issue. No unrelated cleanup or refactors.
- If an Issue is ambiguous, surface the ambiguity. Do not invent requirements.
- Do not add or upgrade dependencies, change architecture, or introduce new infrastructure unless the Issue requires it or you explain the need and get approval.
- Check `git status` and read existing files before writing. Never discard, revert, or overwrite unrelated existing or uncommitted work.
- Never state that tests or checks passed unless you actually ran them.
- Do not commit or push directly to `main` in routine development.
- Do not stage, commit, push, open a Pull Request, or merge unless the human explicitly asks you to do so.
- Humans remain responsible for understanding and approving everything that merges.

## Stack

React + TypeScript + Vite -> FastAPI -> SQLAlchemy + Alembic -> PostgreSQL. Python tooling is pytest and Ruff; scikit-learn is the intended ML library once the expense pipeline works. `docs/architecture.md` is authoritative -- read it before making architectural claims.

## Where to look

Each document is authoritative for its own domain. Read the relevant file rather than inferring its contents. Where the following say something is not established yet, that is the honest state of the project. Say what is missing rather than inventing it.

- `README.md` -- human-facing project overview and documentation index
- `CONTRIBUTING.md` -- branch, Issue, PR, commit, and review workflow
- `docs/architecture.md` -- architecture, component boundaries, domain concepts, technology decisions, current vs. later scope
- `docs/development.md` -- prerequisites, environment setup, dependency and database tooling, Windows vs. WSL differences

## Working on an Issue

Explore -> Plan -> Human Review -> Implement -> Test -> Review Diff -> Pull Request -> Merge

- Retrieve the assigned Issue and its acceptance criteria using available GitHub tooling. If you cannot retrieve them, ask for them -- do not infer the requirements.
- Inspect the relevant repository context before changing code.
- State your assumptions and name any ambiguities.
- Propose a scoped plan and wait for human review before non-trivial implementation.
- Implement the smallest coherent change, then run the appropriate checks and tests.
- Read the resulting diff before handing work back.
- Do not report completion until the acceptance criteria are actually satisfied.

Routine work does not happen on `main`. The team's Git path, branch naming, commit expectations, PR contents, and review policy live in `CONTRIBUTING.md`.

## Development environments

The team develops on both native Windows and WSL2/Ubuntu. Do not assume shell syntax, paths, virtual environment activation, or install commands are identical across them. When you give a command, say which environment it targets. `docs/development.md` has the details.

## Engineering expectations

Write code another undergraduate developer can read and maintain. Use conventional framework patterns, meaningful names, explicit interfaces, validated inputs, useful type annotations, and tests for behavior that matters to the Issue.

Prefer the simplest design that satisfies the current requirements. Avoid premature abstraction, unnecessary indirection, speculative extensibility, or custom infrastructure when established framework patterns are sufficient.

Keep changes small and cohesive. Prefer self-documenting code; comments should explain intent, contracts, tradeoffs, or non-obvious behavior rather than restate what the code already says.

Handle errors deliberately rather than silently ignoring them. Keep behavior deterministic and reproducible where practical, especially in tests and later ML work.

Leave mechanical formatting and style enforcement to each stack's tooling rather than hand-formatting code (Ruff on the Python side; frontend tooling will be documented once selected).
