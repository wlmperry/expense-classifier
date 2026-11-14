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

Issue #17 added the first write endpoint, establishing:

- `POST /expenses` is the collection creation endpoint. A successful request persists one Expense and returns `201 Created`.
- The request schema (`app.schemas.ExpenseCreate`) accepts exactly the four client-owned fields -- `merchant`, `description`, `amount`, `expense_date` -- and rejects any other field, including a client-supplied `id`, through Pydantic's `extra="forbid"` configuration. `id` remains backend/persistence generated, never creation input.
- The response reuses the existing persisted `ExpenseRead` representation established by #13 (`id`, `merchant`, `description`, `amount`, `expense_date`); #17 did not introduce a second persisted-Expense schema.
- `amount` crosses the request boundary as a decimal string, matching the contract's wire-format rule: a JSON number (e.g. `2.75`) is rejected rather than silently coerced. `amount` must be greater than zero and retain no more than two decimal places -- including rejecting a value like `"2.750"` that carries a trailing zero, matching the `scale()` semantics `app.models.Expense` already enforces at the database layer.
- `merchant` and `description` are required and rejected if blank (empty or whitespace-only), without altering the value of an otherwise-valid string.
- `expense_date` is accepted only as an exact `YYYY-MM-DD` string at the HTTP boundary -- a datetime string, a numeric timestamp, or any other non-conforming shape is rejected before Pydantic's own calendar-date validation runs.
- Invalid creation input is rejected through ordinary FastAPI/Pydantic validation (`422 Unprocessable Entity`); no custom error-envelope system was introduced.
- The endpoint persists through the existing `get_db` SQLAlchemy session dependency and commits the created Expense to PostgreSQL; no repository or service abstraction layer was introduced.

Issue #31 added query parameters to the read endpoint, establishing:

- `GET /expenses` accepts `limit` and `offset` for pagination. `limit` must be greater than zero and at most 100; `offset` must be zero or greater, and no greater than PostgreSQL's `bigint` maximum (the type `OFFSET` binds as), since larger values reach the database as a query error rather than a clean `422`. Omitting both returns every persisted Expense, unchanged from before this Issue.
- `merchant` filters to rows whose `merchant` field contains the given text, case-insensitively, anywhere in the field. The text is matched literally -- a `%` or `_` in it is not treated as a SQL wildcard.
- `date_from` and `date_to` filter `expense_date` to an inclusive range. Either can be given alone.
- `sort` accepts `expense_date`, `-expense_date`, `amount`, or `-amount` (a leading `-` means descending); any other value is rejected with `422`. Omitting `sort` keeps the existing default order, by `id`. When `sort` is given, `id` is still used as a tiebreaker so rows with an equal date or amount come back in a consistent order.
- Filtering, sorting, and pagination apply in that order: matching rows are found first, then sorted, then paginated.
- No response envelope or total-count metadata was introduced; the response is still a plain JSON array of `ExpenseRead` objects.

Added on `demo/plaid-ml-mvp` alongside the Plaid/categorizer demo work, ahead of a
filed Issue (the team's usual sign-off for editing/category work was bypassed
under deadline pressure -- see the branch's own history for that decision):

- `PATCH /expenses/{id}` partially updates one persisted Expense. A successful
  request returns `200 OK` with the updated Expense in the existing
  `ExpenseRead` shape; an unknown id returns `404`.
- The request schema (`app.schemas.ExpenseUpdate`) makes every field optional
  -- `merchant`, `description`, `amount`, `expense_date`, `category` -- and
  only the fields actually present in the request body are changed. An
  omitted field keeps its current persisted value.
- Unlike `POST /expenses`, an omitted `category` is **not** re-derived from
  the classifier here: "omitted" means "leave it alone," not "guess for me."
  A client that wants a different category has to supply one explicitly.
- A field sent explicitly as `null` is rejected with `422`, since none of
  these columns are nullable. An empty request body (`{}`) is also rejected
  with `422` rather than treated as a no-op.
- `extra="forbid"` still applies -- an unknown field, including a
  client-supplied `id`, is rejected. Per-field validation (blank-rejection,
  amount wire-format and scale rules, exact `YYYY-MM-DD` dates, valid
  category) otherwise matches `POST /expenses`.
- `id` is capped at PostgreSQL's `integer` maximum, same as `DELETE
  /expenses/{id}`, so an out-of-range id is rejected with `422` instead of a
  database error.

Categorization is established too, as a rule-based baseline rather than a trained model
(Issue #45, building on the classifier added on `demo/plaid-ml-mvp`): `app/categorize.py`
matches keywords in the merchant/description text against a fixed per-category keyword list.
Alongside the category, it reports a **confidence** score derived purely from how many
categories have a distinct-keyword match and how many distinct keywords within the chosen one do
-- not a statistical probability, just a way to flag an ambiguous or unmatched guess as less
trustworthy than a clean match: `0.9` for more than one distinct keyword matching in one,
uncontested category, `0.75` for exactly one distinct keyword matching in one, uncontested
category, `0.5` when more than one category has a match (the first by rule order is still
returned, unchanged from before confidence existed), and `0.2` when nothing matched and the
result fell back to `"Other"`. "Distinct" matters: the same keyword appearing in both `merchant`
and `description` (common for Plaid imports, where both fields can echo the same text) still
counts once, not twice.

`confidence` is `null` whenever `category` isn't the classifier's own current guess -- a
client-supplied `category` on `POST /expenses`, any `PATCH /expenses/{id}` that changes
`category`, a `PATCH` that changes `merchant`/`description` without also setting `category` (the
old score described text that's no longer on the row), or a row that predates this Issue (see
the caveat below) can all mean `null`. A Plaid sync that re-reports an already-imported
transaction as modified reclassifies it the same way `POST /expenses` would, *unless*
`confidence` is already `null` for any of those reasons -- the sync must not silently put the
classifier's guess back over a state it didn't set itself, so it leaves `category` alone in
every `null` case rather than trying to tell them apart. `confidence` is persisted on the
`expenses` row (computed once, like `category` itself, not recomputed on every read) and
included in `ExpenseRead`. A keyword match fully contained inside a longer match anywhere in the
text (e.g. the standalone `"airlines"` keyword inside the `"united airlines"` keyword, or
`"uber"` inside `"uber eats"`) is discarded before scoring, so one specific phrase can't inflate
its own hit count or make an unrelated category look ambiguous. The machine-learned classifier
scikit-learn is meant for (see "Not decided yet" below) would replace this baseline and its
confidence heuristic together, not layer on top of them.

**Caveat for rows that predate this Issue:** the migration that added `confidence` set it to
`null` for every pre-existing row, including ones the classifier itself categorized before this
existed. `null` is not retroactively accurate for those rows the way it is from this Issue
forward -- there is no reliable way to tell, after the fact, which pre-existing categories were
a human's choice and which were the classifier's unreviewed guess, so none were backfilled
(doing so risked silently overwriting a human correction that happened to agree with what the
classifier would guess today). Treat `null`/`"—"` on a row from before this Issue shipped as
"unknown," not as "a human definitely chose this."

**Specific categories (Issue #50):** the original 7 broad categories were replaced with 20
specific ones (e.g. "Food & Dining" became Groceries, Restaurants & Bars, Coffee Shops, and Food
Delivery). `CATEGORIES` in `app/categorize.py` is the single backend source for the list: the
API's `Literal` validation and the `ck_expenses_category_allowed` database check constraint are
both built from it, and `frontend/src/types.ts` mirrors it by hand. Rule order in
`_KEYWORD_RULES` is also the tie-break order when more than one category matches. Migration
`3c86f19d4985` converted existing rows: a row with non-null `confidence` was re-run through the
new rules, and a row with `null` `confidence` was never re-guessed but mapped to a fixed new name
within its old group (Food & Dining to Restaurants & Bars, Transportation to Rideshare & Transit,
Housing & Utilities to Utilities, Shopping to General Merchandise, Entertainment to Movies &
Events, Health & Fitness to Medical). Per the caveat above, that includes rows from before
confidence existed, so their specific name is a default, not a guess. The downgrade maps each new
name back to its old group.

These are the established Expense-resource API decisions. Authentication and deployment
decisions follow below.

Authentication is established too, as a stopgap rather than a long-term design: every route
except `GET /` requires a shared bearer token (`app/auth.py`, `API_AUTH_TOKEN`), checked
against a single value every client uses. This is not a user/account system -- there is still
no concept of a user who owns an Expense. Now that the frontend is deployed too (Issue #42),
the token is baked into its built JS bundle (`VITE_API_AUTH_TOKEN`) and readable by anyone who
opens the site in DevTools, so it does **not** protect the shared dataset from a visitor who
goes looking -- it only deters casual/bot abuse of the raw API by a client that never loads the
frontend. See Issue #44 for real protection (a login, or a read-only public demo). A
real user/account auth system remains undecided.

Backend deployment is established too (Issue #36): the database is hosted on Supabase
(managed PostgreSQL), reached through its **session-mode** connection pooler rather than its
transaction-mode one -- this app's SQLAlchemy `sessionmaker`/`Session`-per-request pattern
relies on a connection behaving continuously for the life of a request, which transaction-mode
pooling does not support. The backend itself runs on Render's free web-service tier
(`uvicorn app.main:app`, Virginia/US East region), built and deployed from this repository's
`main` branch; a free-tier instance spins down after about 15 minutes idle, with a roughly
one-minute cold start on the next request, which is acceptable for a class demo but not for
production use. `DATABASE_URL`, `PLAID_CLIENT_ID`/`PLAID_SECRET`/`PLAID_ENV`, and
`API_AUTH_TOKEN` are configured directly in Render's dashboard rather than committed anywhere.

Frontend deployment is established too (Issue #42): the React/Vite build is hosted as a
separate Render **Static Site**, built from this same repository's `frontend/` directory
(`npm install && npm run build`, publishing the `dist/` folder), rather than a different
platform such as Vercel -- this keeps the whole project's deploy surface in one dashboard and
avoids a second GitHub App installation. `VITE_API_BASE_URL` and `VITE_API_AUTH_TOKEN` are set
at build time in that service's environment to point at the deployed backend and match its
`API_AUTH_TOKEN`. `CORSMiddleware`'s `allow_origins` includes the deployed frontend's origin
alongside `http://localhost:5173`, which stays for local development.

If `VITE_API_BASE_URL` is ever missing or misspelled in Render's build environment, the build
still succeeds -- `frontend/src/config.ts` falls back to `http://127.0.0.1:8000` -- but every
visitor's browser then tries to reach its own localhost and the site only shows fetch errors.
Double-check that variable is set correctly after any change to the Static Site's environment.

## Not decided yet

`GET /expenses`, `POST /expenses`, `PATCH /expenses/{id}`, and `DELETE /expenses/{id}`, and their request/response schemas, are established (see "Established API decisions" above). An editing UI on the frontend is also established (the same PATCH endpoint, driving an edit form in `App.tsx`/`ExpenseForm.tsx`). Backend and frontend deployment are established too (see above). Other endpoints, further request/response schemas, and repository layout remain undecided. They will be documented here as they are established, rather than guessed at now.

Schema and design for Receipt, Transaction, and every other concept listed under "Deferred from this contract" above remain entirely undecided. Categorization itself is no longer in that list -- see "Established API decisions" above for the rule-based baseline and its confidence score; only the later machine-learned classifier remains undecided.
