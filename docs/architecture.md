# Architecture

**Status: proposed.** This describes the system the team has agreed to build toward, not one that exists yet.

Change it through an Issue and a pull request, not in passing.

## Overview

Expense Classifier records and categorizes expenses, and presents spending summaries back to the user. It is a conventional three-layer web application: a browser frontend, an HTTP API, and a relational database. Machine learning is a later addition to the categorization step inside the backend, not a separate service.

## Core domain concept

An **Expense** is the application's canonical unit of spending and the primary unit the system categorizes.

An Expense may eventually originate from manual entry, imported financial records, receipts, or other sources. Regardless of source, Expense is the stable application-level unit that categorization operates on.

A future `Transaction` concept may represent an upstream financial-source record, such as something imported from a bank. Transaction is not part of the walking skeleton, and the exact relationship between Transactions and Expenses is deliberately undecided. Do not model or design that relationship, including its schema, without an Issue that asks for it.

## Request path

The current technical target is the **first walking skeleton**--one thin slice proving every layer can talk to the next, in both directions:

```text
React + TypeScript  ->  FastAPI  ->  SQLAlchemy  ->  PostgreSQL
     (browser)         (HTTP/JSON)     (ORM)          (storage)
React + TypeScript  <-  FastAPI  <-  SQLAlchemy  <-  PostgreSQL
```

A minimal expense is accepted by the frontend, validated by the API, persisted through the ORM, retrieved again, and displayed. Nothing beyond that is in scope yet.

## Component responsibilities

**Frontend -- React + TypeScript, built with Vite**

- Renders the user interface and owns client-side state.
- Talks to the backend over HTTP with JSON.
- Owns presentation and client-side interaction logic, but not authoritative business rules.
- Never reaches the database directly.

**Backend -- Python + FastAPI**

- Owns the HTTP surface: routing, request and response shapes, and validation of anything arriving from a client.
- Owns business logic, and later the categorization step.
- Is the only component that talks to the database.

**Persistence -- PostgreSQL, via SQLAlchemy and Alembic**

- SQLAlchemy defines the models and mediates queries, so application code does not write raw SQL by default.
- Alembic owns schema changes, so the schema evolves in ordered, reviewable steps rather than by hand.

## Technology choices

| Technology | Role |
| --- | --- |
| React | Frontend UI library |
| TypeScript | Type safety across the frontend |
| Vite | Frontend build tool and development server |
| Python | Backend language |
| FastAPI | Backend web framework, including request validation |
| PostgreSQL | Relational database |
| SQLAlchemy | ORM and database access layer |
| Alembic | Database schema migrations |
| pytest | Backend tests |
| Ruff | Python linting and formatting |
| scikit-learn | ML library for later expense categorization |

## Current scope versus later directions

**In scope now**

- One expense accepted, validated, persisted, retrieved, and displayed end to end.

**Later, and deliberately not designed yet**

- Machine-learned categorization with scikit-learn, once the expense pipeline works.
- Receipt OCR and item-level extraction.
- Richer analytics, summaries, and dashboards.

Nothing in the "later" list is committed to a design. Do not build toward it, and do not add dependencies for it, without an Issue that asks for it.

## Not decided yet

API endpoints, database schema, repository layout, and deployment are undecided. They will be documented here as they are established, rather than guessed at now.
