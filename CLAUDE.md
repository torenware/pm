# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the application

```sh
./scripts/start-macos.sh   # macOS
./scripts/start-linux.sh   # Linux
./scripts/start-windows.ps1  # Windows PowerShell
```

Open <http://localhost:8000>. Sign in with `user` / `password`. Sessions expire after 8 hours.

Stop with the matching `stop-*` script. Board data persists in `data/pm.db` (git-ignored).

### Backend tests

```sh
cd backend
uv run pytest                        # all tests
uv run pytest tests/test_board_api.py  # single file
```

### Frontend

```sh
cd frontend
npm run lint
npm run test:unit
npm run test:e2e
# Against the Docker application:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
```

## Architecture

Single Docker Compose service. FastAPI serves both the REST API and the statically exported Next.js frontend at `/`.

### Backend (`backend/`)

- `app/main.py` — `create_app()` factory wires all dependencies; `app` module-level instance reads env vars. All API routes are defined here.
- `app/database.py` — `Database` class wraps SQLite. `initialize()` runs schema migrations and seeds the MVP user/board/columns on first run (idempotent via `INSERT OR IGNORE`). WAL mode enabled. Foreign keys enforced per connection. Migrations tracked in `schema_migrations` table.
- `app/board.py` — `BoardStore` handles all board mutations. Card moves use a temporary position offset to avoid unique-constraint collisions during reorder. `ImmediateTransaction` context manager provides `BEGIN IMMEDIATE` transactions for write operations.
- `app/auth.py` — `SessionStore` manages HMAC-signed session cookies stored in SQLite. `require_session` returns a FastAPI dependency for protected routes.
- `app/ai.py` — `KodeKloudClient` (protocol: `AIClient`) calls the KodeKloud OpenAI-compatible API (`gpt-oss-120b`). `ask_board()` sends current board state + conversation history and expects a structured JSON response (`StructuredAIResponse`) with `assistantText` and typed `operations`.

### Frontend (`frontend/`)

Next.js 16 with static export (`output: "export"`). The exported `out/` directory is copied into `backend/app/static/` during the Docker build.

- `src/lib/board-api.ts` — all backend API calls (typed fetch wrappers)
- `src/lib/ai-api.ts` — AI board endpoint call
- `src/lib/kanban.ts` — pure board state logic (no API calls)
- `src/components/AuthGate.tsx` — wraps the app; shows login form when no session exists, redirects to login on 401
- `src/components/KanbanBoard.tsx` — main board with drag-and-drop (`@dnd-kit`)
- `src/components/AIChatSidebar.tsx` — AI chat; holds conversation history in React state only (never persisted, cleared on logout/reload)

### AI board operations

The AI response contains `assistantText` plus a list of explicit typed operations (`create_card`, `edit_card`, `delete_card`, `move_card`, `rename_column`). `BoardStore.apply_operations()` validates and applies all operations atomically — one invalid operation rolls back the entire set. Conversation history is browser-only; never written to SQLite.

### Environment

Root `.env` file (not committed):
- `KK_BASE_URL`, `KK_API_KEY` — KodeKloud AI credentials (server-side only, never sent to browser)
- `SESSION_SECRET` — stable secret keeps sessions valid across container recreation
- `APP_PORT` — host port (default `8000`)

### Database schema

Five tables: `users`, `boards`, `board_columns`, `cards`, `sessions`. Board columns are fixed to five (`backlog`, `discovery`, `progress`, `review`, `done`) — names can change but the `column_key` is immutable. Card ordering uses integer `position` with unique constraint per column; moves temporarily offset positions to avoid constraint violations.

## Coding standards

- No over-engineering, no unnecessary defensive programming, no extra features
- No emojis
- Identify root cause before fixing; prove with evidence
- Keep README minimal
