# Aashan Backend

Aashan is a privacy-first personal finance MVP with “Goldfish Memory”: it learns spending patterns, then intentionally forgets individual transactions.

## Architecture

```text
AA / CSV / SMS
      ↓
Normalization → Categorization → Aggregation
      ↓
DELETE RAW DATA
      ↓
Aggregate-only SQLite database
      ↓
Dashboard / insights / alerts
```

The legacy direct SMS/demo paths remain aggregate-only. Unified CSV and Setu
imports now persist only the canonical, user-owned transaction fields needed
for financial management; raw CSV payloads, raw SMS bodies, and full Setu FI
payloads are not persisted. The privacy endpoints never return raw source
payloads.

Storage is selected through a repository boundary:

```text
FastAPI/services → app.database.db facade → Repository
                                      ├── SQLiteRepository (local/demo)
                                      └── PostgresRepository (Supabase beta)
```

Database schema changes are versioned under `migrations/sqlite/` and
`migrations/postgres/`. SQLite startup migrations preserve the legacy global
demo tables and migrate their existing data into the local owner scope without
deleting the database.

## Local setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

## Mock AA mode

`MOCK_MODE=true` is the default. It uses clearly labelled `MOCK / DEMO DATA`, generates 75 fake transactions across several months, and needs no Setu account or banking credentials.

Run the full demo with `POST /api/demo/run`, or walk through the mock consent flow:

1. `POST /api/aa/mock/consent`
2. `POST /api/aa/mock/approve?consent_id=...`
3. `POST /api/aa/mock/fetch?consent_id=...`

## Setu sandbox mode

Set `MOCK_MODE=false`, then configure `SETU_BASE_URL`, `SETU_CLIENT_ID`, `SETU_CLIENT_SECRET`, and `SETU_PRODUCT_INSTANCE_ID` in `.env`. A missing value returns a clear configuration error; the application never silently falls back to mock data.

The Setu adapter follows the documented flow: create consent, wait for approval, create a data session, receive a webhook, then fetch `/sessions/:id`. Configure the public notification URL in Setu Bridge to point to `/api/webhooks/setu`, and configure the redirect URL through `REDIRECT_URL`.

## Ingestion and APIs

- `POST /api/ingest/csv` accepts `date`, `description`, `amount`, `mode`, and `transaction_type` plus common title-case aliases.
- `POST /api/ingest/sms` parses one SMS and immediately sends it through normalize → categorize → aggregate → forget.
- `POST /api/budgets` accepts `{ "budgets": { "Food": 5000, "Shopping": 4000 } }`.
- Dashboard endpoints are under `/api/dashboard/*`.
- `POST /api/insights/query` answers basic questions using aggregate JSON only.
- `GET /api/dashboard/privacy` proves raw transactions are not persisted.

### Unified ingestion foundation

CSV and real Setu FI data now converge through the same source-neutral path:

```text
source adapter
→ owned import
→ processing job/checkpoints
→ normalized transaction input
→ candidate
→ classification
→ confirmed canonical transaction
→ existing process_raw_rows() kernel
→ aggregate snapshot
```

The adapters live under `app/services/ingestion/`. PDF and Android SMS
adapters are intentionally not implemented yet. CSV and trusted Setu imports
create canonical transactions; strong external IDs are idempotently rejected
when already present. Ambiguous future sources can remain candidates without
affecting aggregates.

New ownership-aware contracts include:

- `GET /api/imports` and `GET /api/imports/{id}`
- `GET /api/transaction-candidates`
- `POST /api/transaction-candidates/{id}/review`
- `GET /api/transactions`
- `POST /api/transactions/{id}/review`
- `POST /api/merchant-rules`

Transaction lifecycle, classification, budget inclusion, transfer state, and
duplicate state are stored separately. Transfers are excluded from income and
spending calculations. Budget-excluded rows remain financial transactions but
are excluded from budget-eligible category totals.

Unknown transaction descriptions use a lazy `sentence-transformers` fallback with `all-MiniLM-L6-v2`. Rule matches are attempted first; semantic similarity is used only when no merchant or keyword rule matches. Configure it with `AASHAN_ENABLE_EMBEDDINGS` and `AASHAN_EMBEDDING_THRESHOLD`.

Credits remain income: `total_spending` equals debit-only spending, while `total_credit` and `net_cash_flow` are reported separately.

## Testing

```bash
pytest
```

The test suite runs entirely in mock mode and does not need Setu credentials.

## Supabase Auth and ownership

Set `AUTH_REQUIRED=true` for an authenticated environment. Production also
enables authentication automatically when `ENVIRONMENT=production`. Configure
`SUPABASE_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, and either the
server-side JWT secret or the Supabase JWKS configuration used by PyJWT. Keep
`SUPABASE_SERVICE_ROLE_KEY` server-side; it is never returned by
`GET /api/auth/config`.

Supabase Auth owns email/password and Google OAuth credentials. The frontend
obtains the Supabase session, sends its access token as `Authorization: Bearer
<token>`, and FastAPI derives ownership from the validated JWT `sub` claim.
The backend does not accept a request-body `user_id`.

Useful contracts:

- `GET /api/auth/config` returns safe client configuration.
- `GET /api/auth/session` validates a Supabase access token.
- `POST /api/auth/logout` acknowledges client-side Supabase logout.
- `DELETE /api/auth/account` is reserved for the complete privacy-deletion workflow; it does not falsely claim deletion yet.

In local development, `AUTH_REQUIRED=false` uses a fixed local demo owner so
the existing mock and CSV tests remain runnable without Supabase. Owned
dashboard, budget, ingestion, insights, and Setu consent routes still use the
same dependency and become strict when authentication is enabled.
