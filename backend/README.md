# Lens Shtar — FastAPI backend

Python API for **Supabase-authenticated users**, **per-session Gemini API keys** (memory only, never persisted), **statement upload + analysis**, and **dashboard JSON** for the frontend.

There is **no server-side Gemini key**. PDF extraction and the optional AI narrative use **only** the key from `session_store[user_id]` gathered via `POST /api/settings/set-api-key`.

## Prerequisites

- Python 3.11+
- Supabase project (frontend handles Google login)
- Supabase **JWT Secret** for verifying `Authorization: Bearer <access_token>`
- Users bring their own **Google AI Studio / Gemini API key** (stored in server memory per session)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Environment

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Anon key (frontend); not used for JWT verification |
| `SUPABASE_JWT_SECRET` | **Required** — verify user JWTs |
| `SUPABASE_JWT_AUDIENCE` | Optional (default `authenticated`) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `SESSION_INACTIVITY_SECONDS` | Idle timeout; drops in-memory session (including Gemini key) |
| `VIDEO_PLACEHOLDER_ENABLED` | Exposed in `/api/settings/status` for UI |
| `MAX_UPLOAD_MB` | Max upload size (default `12`, cap 30) |
| `GEMINI_MODEL` | Model id for REST (default `gemini-2.0-flash`) |
| `GEMINI_TIMEOUT_SECONDS` | Request timeout (30–300, default 120) |
| `GEMINI_AI_SUMMARY_ENABLED` | If `false`, skips extra Gemini narrative call (still rule-based summary) |

Minimal `.env`:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Authentication

1. User signs in with Supabase (e.g. Google) in the browser.
2. Frontend sends every request with `Authorization: Bearer <access_token>`.
3. Backend verifies JWT (HS256) with `SUPABASE_JWT_SECRET` and uses `sub` as `user_id`.

## Session Gemini key (memory only)

- `POST /api/settings/set-api-key` — validates format, stores key in **`session_store[user_id]`** only.
- Never written to disk or database; never returned on any response.
- `GET /api/settings/status` — `{ "has_api_key", "video_placeholder_enabled" }`.
- `POST /api/settings/clear-api-key` — removes the key from memory.
- Process restart or idle timeout clears keys.

## Analysis pipeline

**Upload** (`POST /api/upload`, requires auth + session key):

| Type | Processing |
|------|------------|
| `.pdf` | Sent to **Gemini** with the **user’s** API key; structured JSON transaction extraction |
| `.csv`, `.xls`, `.xlsx` | Parsed with **pandas** locally (no Gemini for parsing) |

Then (for all types, **no AI**):

- Validate, dedupe, normalize transactions
- **Financial engine**: income, expenses, savings, savings rate, category totals, UPI spend, EMI hints, recurring patterns
- **Money leaks**: duplicate subscription charges, repeated small spends, subscription audit hints
- **Suggestions**: Quick Wins, Monthly Optimization, Long-Term (rule-based)
- **Optional AI summary**: second Gemini call with **aggregates only** — explanation, not recalculation. On failure, falls back to a deterministic text summary.

Results are stored **in memory** keyed by `file_id` (UUID), scoped to `user_id`.

**Dashboard** (`GET /api/dashboard/{file_id}`, auth required, **API key not required**):

Returns KPIs, charts, leaks, suggestions (three buckets), transactions, `ai_summary`, and metadata. Returns **404** if the id is unknown or belongs to another user.

## Endpoints

| Method | Path | Auth | Session Gemini key |
|--------|------|------|--------------------|
| GET | `/api/health` | No | — |
| POST | `/api/settings/set-api-key` | Yes | — |
| GET | `/api/settings/status` | Yes | — |
| POST | `/api/settings/clear-api-key` | Yes | — |
| POST | `/api/upload` | Yes | **Required** |
| GET | `/api/dashboard/{file_id}` | Yes | No |

Query params:

- `POST /api/upload?include_ai_summary=true|false` — default `true` (if `GEMINI_AI_SUMMARY_ENABLED` is on).

## Error handling (high level)

| Situation | Typical response |
|-----------|------------------|
| Missing/invalid Supabase JWT | 401 |
| Upload without session Gemini key | 400 `API key required` |
| Invalid or unauthorized Gemini key | 401 / message from Google |
| Gemini overload / failure | 502 + safe message; summary path falls back when possible |
| File too large | 413 |
| Unsupported type | 415 |
| Bad CSV/layout / no transactions | 422 |

## Frontend flow

**Settings → Upload → Dashboard**

1. Obtain Supabase session + access token.
2. `POST /api/settings/set-api-key` with user’s Gemini key.
3. `POST /api/upload` with `multipart/form-data` `file` and Bearer token.
4. Read `file_id` from response; navigate to dashboard data via `GET /api/dashboard/{file_id}`.

Video UI: use `video_placeholder_enabled` from settings status (this API does not host video).
