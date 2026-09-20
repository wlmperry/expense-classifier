# Architecture

**Status: proposed.** This describes the system the team has agreed to build toward, not one that exists yet.

Change it through an Issue and a pull request, not in passing.

## Overview

Expense Classifier records and categorizes expenses, and presents spending summaries back to the user. It is a conventional three-layer web application: a browser frontend, an HTTP API, and a relational database. Machine learning is a later addition to the categorization step inside the backend, not a separate service.

## Core domain concept

An **Expense** is the application's canonical unit of spending and the primary unit the system categorizes.

An Expense may eventually originate from manual entry, imported financial records, receipts, or other sources. Regardless of source, Expense is the stable application-level unit that categorization operates on.

The walking skeleton fixes that unit's granularity and the fields it carries. See the Expense contract below.

A future `Transaction` concept may represent an upstream financial-source record, such as something imported from a bank. Transaction is not part of the walking skeleton, and the relationships among Expenses, receipts, and Transactions are deliberately undecided. Do not model or design those relationships, including their schema, without an Issue that asks for it.

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

## The walking-skeleton Expense contract

A **contract** here is an agreed cross-layer representation: the fields an Expense has, what each one means, and the rules every layer must preserve. Each layer encodes an Expense in whatever way is idiomatic for it -- a TypeScript interface, a Pydantic model, a SQLAlchemy model, a PostgreSQL table -- but no layer may quietly redefine what an Expense *is*. Where an encoding disagrees with this section, the encoding is wrong.

The contract exists so that frontend, API, and persistence work can proceed as separate Issues without each one inventing its own Expense. It was accepted in Issue #10; that Issue is the planning record, and this section is the durable source of truth. Later Issues implement this contract rather than redefining it, and changing it takes an Issue and a pull request like any other architecture decision here.

### What an Expense represents

For the walking skeleton, an Expense is **one individual purchased good or service**, entered by hand. It is not a receipt, and it is not a bank or card transaction.

```text
Receipt / financial transaction
        |
        | may eventually contain or correspond to
        v
Individual Expenses
```

A receipt may eventually correspond to multiple Expenses representing its individual purchased goods or services. The exact receipt-to-Expense mapping remains deliberately undecided. This contract defines only the Expense side of that picture; the rest of the relationship stays undecided, as described under "Core domain concept" above.

The granularity is deliberate. Categorization is the point of the project, and an individual purchase preserves substantially more useful categorization information than a receipt total alone.

### Creation input versus persisted Expense

The contract has two shapes, differing by exactly one field.

**Expense creation input** -- what a client supplies:

```json
{
  "merchant": "DOLLAR GENERAL STORE #16600",
  "description": "S RED BULL 8.4C",
  "amount": "2.75",
  "expense_date": "2026-08-29"
}
```

**Persisted and retrieved Expense** -- what the system stores and returns:

```json
{
  "id": 1,
  "merchant": "DOLLAR GENERAL STORE #16600",
  "description": "S RED BULL 8.4C",
  "amount": "2.75",
  "expense_date": "2026-08-29"
}
```

`id` is generated by the backend and persistence layer. It is never creation input, and a client does not choose it.

### Fields

| Field | JSON representation | Meaning |
| --- | --- | --- |
| `id` | integer | Unique identifier, generated on persistence. Not creation input. |
| `merchant` | string | Where the good or service was purchased. |
| `description` | string | What was purchased. |
| `amount` | decimal string | The individual line item's monetary amount, as entered from the source receipt or record. |
| `expense_date` | ISO `YYYY-MM-DD` string | The calendar date on which the purchase occurred. |

`description` earns its place: a merchant alone cannot tell later categorization what was bought, because one merchant sells goods and services across many categories. It is required for that reason, not as an optional note.

`expense_date` is a calendar date, not a timestamp -- no time of day and no timezone.

### `amount` across the layers

`amount` is the field most likely to be implemented wrongly, so it is specified per layer.

| Layer | Representation | Example |
| --- | --- | --- |
| JSON and API boundary | decimal **string** | `"2.75"` |
| Backend and domain | exact decimal type | `Decimal("2.75")` |
| Database and ORM | exact decimal / fixed-point column | a numeric type carrying two decimal places |

And explicitly not:

| Layer | Wrong | Why |
| --- | --- | --- |
| JSON and API | `2.75` as a JSON number | JSON numbers are ordinarily decoded as binary floating point, including by `JSON.parse` in the TypeScript frontend. That reintroduces exactly the problem the string form avoids. |
| Backend and domain | a binary floating-point `float` | Most decimal money values have no exact binary representation. |
| Database and ORM | `"2.75"` in a text column | A text column stores money as prose: no numeric type, no precision or range guarantees, no arithmetic. |

The wire format and the storage format are separate requirements. A decimal string on the wire does not mean a string column in the database.

The value is the item's amount **as entered from the source record**. If the receipt line reads:

```text
S RED BULL 8.4C    $2.75
```

then `amount` is `2.75`. Tax is not folded into it, allocated across it, or used to adjust it in any way. Receipt-level tax, subtotal, and total are separate future concerns and do not change what this field means.

`amount` must be greater than zero and carry no more than two decimal places. Zero and negative amounts -- refunds, credits, and other balance-reducing adjustments -- are outside this contract. That is a deferral, not a design: no refund or credit model is proposed here.

### Validation

| Layer | Role |
| --- | --- |
| Frontend | Supplemental. Improves the manual-entry experience; never authoritative. |
| FastAPI backend | **Authoritative** for anything arriving from a client. |
| Persistence | Reinforces structural invariants through appropriate column types and constraints. |

Frontend validation can be bypassed, so the backend assumes it was. The walking-skeleton rules:

- `merchant` -- required, non-blank.
- `description` -- required, non-blank.
- `amount` -- required, greater than zero, no more than two decimal places, a decimal string across the JSON boundary.
- `expense_date` -- required, a valid calendar date.
- `id` -- generated by the application, not accepted as creation input.

### Deferred from this contract

These are not walking-skeleton Expense fields or concerns, and must not be added without an Issue that asks for them:

- tax, receipt subtotal and total, and allocation of receipt-level tax to Expenses;
- receipt or store transaction and reference numbers;
- Receipt entities, receipt grouping, and receipt images;
- a `Transaction` domain model;
- OCR and automatic line-item extraction;
- categories and ML predictions;
- user or account ownership;
- currency and multi-currency support;
- merchant normalization and canonical merchant identities;
- timestamps such as `created_at` and `updated_at`;
- structured product or item entities;
- analytics and derived financial values;
- zero, negative, and otherwise adjusting amounts.

Deferring OCR does not stop anyone from typing a line item in by hand. That is the walking-skeleton entry path.

This contract also does not choose API endpoint paths, HTTP methods, status codes, SQLAlchemy model structure, repository layout, or frontend component design. Those belong to the Issues that implement them.

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

## Established schema decisions

Issue #12 encoded the Expense contract above in SQLAlchemy and PostgreSQL, establishing:

- Table name: `expenses`.
- `id`: an integer primary key, generated by PostgreSQL, never supplied as creation input.
- `merchant` and `description`: required (`NOT NULL`), reinforced with a `CHECK` constraint rejecting empty or space-only values.
- `amount`: an unconstrained PostgreSQL `NUMERIC` column -- no fixed precision or scale. A fixed-scale `NUMERIC(p, s)` would silently round a value carrying more than `s` decimal places instead of rejecting it, which would violate the contract's "no more than two decimal places" rule. Two `CHECK` constraints reinforce the invariants explicitly instead: `amount > 0`, and `scale(amount) <= 2` (rejects, rather than rounds, a value with more than two decimal places retained in storage -- PostgreSQL's `scale()` counts the digits actually stored, including a trailing zero such as in `2.750`, not the mathematically significant ones).
- `expense_date`: a PostgreSQL `DATE` column -- no time component, no timezone.

These are schema/persistence decisions only. They do not establish API endpoint shapes, Pydantic schemas, or any repository/service abstraction.

## Established API decisions

Issue #13 added the first read endpoint on top of Issue #12's schema, establishing:

- `GET /expenses` returns `200 OK` with a JSON array of persisted Expenses, each carrying exactly the persisted-Expense contract fields: `id`, `merchant`, `description`, `amount`, `expense_date`. An empty persistence state returns `[]`, not an error.
- The API response schema (`app.schemas.ExpenseRead`) is a Pydantic model distinct from the SQLAlchemy `app.models.Expense` ORM class, built from ORM objects via Pydantic v2's `from_attributes`. The name leaves room for a future `ExpenseCreate` once a creation endpoint exists.
- `amount` is typed as Pydantic `Decimal`, not `float`, so it serializes as a JSON string (e.g. `"2.75"`), matching the contract's wire-format rule -- never a JSON number.
- `expense_date` is typed as Pydantic `date`, which serializes to ISO `YYYY-MM-DD`, matching the contract.
- The endpoint queries through the existing `get_db` SQLAlchemy session dependency; no repository or service abstraction layer was introduced for this minimal read path.

These are the only API decisions established so far. Creation (`POST`), pagination, filtering, sorting, and authentication remain undecided.

## Not decided yet

The read side of `GET /expenses` and its response schema are established (see "Established API decisions" above). Creation and other endpoints, further request/response schemas, repository layout, and deployment remain undecided. They will be documented here as they are established, rather than guessed at now.

Schema and design for Receipt, Transaction, categorization, and every other concept listed under "Deferred from this contract" above remain entirely undecided.
