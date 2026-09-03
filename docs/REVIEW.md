# Code Review

This review covers the full codebase as of Part 10 completion. Issues are grouped by severity.

---

## Bugs

### 1. SQLite connection leak in `BoardStore` and `SessionStore`

**Files:** `backend/app/board.py`, `backend/app/auth.py`

Python's `sqlite3.Connection` used as a context manager (`with connection:`) manages **transactions** only — it calls `commit()` on exit and `rollback()` on exception, but does **not close the connection**. The `Database.connect()` method creates a new connection on every call, and callers that use it without an explicit `close()` are leaking connections.

Affected locations:
- `BoardStore.get()`, `rename_column()`, `edit_card()` — use `with self._database.connect() as connection:` with no close
- `SessionStore.create()`, `get()`, `delete()` — same pattern

Contrast with `Database.initialize()` and `ImmediateTransaction.__exit__()`, which both call `connection.close()` explicitly — these are correct.

Under CPython's reference counting this rarely causes observable problems, but it is a genuine resource management error and a latent risk on any runtime without deterministic GC.

**Fix:** Add an explicit `connection.close()` in a `finally` block, or redesign `Database.connect()` as a context manager that closes on exit.

---

### 2. `KanbanColumn` title state drifts after external rename

**File:** `frontend/src/components/KanbanColumn.tsx:27`

```ts
const [title, setTitle] = useState(column.title);
```

`useState` initialises only on the first render. When an AI operation renames a column, `KanbanBoard` calls `setBoard(result.board)` and passes the new `column` prop to `KanbanColumn` — but the local `title` state is never updated. The column title input continues showing the old name until the page is reloaded.

**Fix:** Add a `useEffect` that syncs local state when the prop changes:
```ts
useEffect(() => { setTitle(column.title); }, [column.title]);
```

---

### 3. Wrong error message on initial board load failure

**File:** `frontend/src/components/KanbanBoard.tsx:77`

When the initial `getBoard()` call fails with a non-401 error, the error state is set to:

> "Your change could not be saved. Please try again."

No change was attempted — the board simply failed to load. The same string is used correctly for mutation failures elsewhere, but it is misleading here.

---

### 4. Stale scaffold test

**File:** `backend/tests/test_main.py:24`

`test_root_serves_temporary_page_that_calls_health_api` asserts that the root path returns HTML containing `"Project Management MVP"` and `fetch("/api/health")`. These strings are from the original scaffold placeholder, which was replaced by the Next.js static export in Part 3. The test only passes today because `backend/app/static/` contains whatever content was last placed there; against a clean build from source it would fail or test nothing meaningful.

---

## Security

### 5. Container runs as root

**File:** `Dockerfile`

There is no `USER` directive. The application process runs as root inside the container. A process escape would have full container privileges.

**Fix:** Add a non-root user and switch to it before the `CMD` line:
```dockerfile
RUN useradd --create-home appuser
USER appuser
```

### 6. No `.dockerignore`

The build context includes the entire repository tree: `node_modules/`, `data/pm.db`, `test-results/`, `.git/`, and any local `.env` files. This slows builds and risks including secrets or large binary files in the image layer.

**Fix:** Add a `.dockerignore` that at minimum excludes `data/`, `.git/`, `test-results/`, `frontend/node_modules/`, and `frontend/.next/`.

---

## Code Quality

### 7. Card move logic duplicated between `move_card` and `_move_card_operation`

**File:** `backend/app/board.py`

`BoardStore.move_card()` (lines 175–212) and `BoardStore._move_card_operation()` (lines 303–340) implement the identical position-shift algorithm: calculate the temporary offset, shift affected columns, write source positions, conditionally write target positions, then update `column_id`. The duplication is ~30 lines and any fix to one must be mirrored in the other.

`move_card` should delegate to `_move_card_operation` (or a shared internal method) rather than repeating the logic.

### 8. `createId` is dead code

**File:** `frontend/src/lib/kanban.ts:164`

`createId` was used in the frontend-only prototype to generate local IDs. The connected application generates all identifiers on the backend (UUID4). `createId` is exported but never imported anywhere in the current codebase.

### 9. `initialData` belongs in test fixtures, not production code

**File:** `frontend/src/lib/kanban.ts:18`

`initialData` is a static board with hardcoded frontend-only IDs (`col-backlog`, `card-1`, etc.). It is never used in the running application — only by frontend unit tests. Leaving it in the production module is misleading and adds weight to a file that should only contain board logic.

**Fix:** Move `initialData` into a test-only fixture file, e.g. `frontend/src/test/fixtures.ts`.

### 10. Duplicate board loading in `KanbanBoard`

**File:** `frontend/src/components/KanbanBoard.tsx:54–86`

There is a `loadBoard` function (used by the retry button) and a `useEffect` that also calls `getBoard()` directly. The two paths duplicate the 401-detection and error-state logic. The `useEffect` should call `loadBoard()` so the paths stay consistent.

### 11. Redundant expiry check in `SessionStore.get()`

**File:** `backend/app/auth.py:62–76`

The SQL query already filters out expired sessions with `expires_at > ?`. The subsequent Python check `if expires_at <= self._now(): return None` can never be true for a row the query returned (unless time runs backwards). The second check is harmless but adds confusion about what the first check is doing.

---

## Testing Gaps

### 12. `KanbanBoard` unit tests don't cover drag-and-drop mutations

**File:** `frontend/src/components/KanbanBoard.test.tsx`

`moveCard` is included in the vi.mock setup but no test triggers a drag-end event or verifies that `persistCardMove` is called with the right arguments. The drag flow is covered by Playwright, but unit-test coverage of the optimistic-update and rollback logic for moves is absent.

### 13. `board-api.test.ts` passes `headers: undefined` as expected value

**File:** `frontend/src/lib/board-api.test.ts:26–28`

The `getBoard` test asserts `fetch` was called with `{ headers: undefined }`. This confirms the implementation detail that `requestBoard` spreads `init?.headers` even when `init` is undefined, rather than asserting the meaningful API contract (path and no body). The assertion would silently pass even if the headers were wrong.

---

## UX Issues

### 14. Card deletion has no confirmation

**File:** `frontend/src/components/KanbanCard.tsx:99–105`

Clicking "Remove" immediately and irreversibly deletes the card. There is no undo. A confirmation step (inline prompt or `window.confirm`) would prevent accidental deletion.

### 15. Card edit form does not auto-focus

**File:** `frontend/src/components/KanbanCard.tsx:46`

When a user clicks "Edit", the inline form appears but neither the title input nor any other field receives focus. The user must click again before typing.

### 16. AI conversation history has no length cap

**File:** `backend/app/main.py:49`, `frontend/src/components/AIChatSidebar.tsx`

The `history` field in `AIBoardRequest` is an unbounded list. Over a long session, the full conversation history is serialised into the JSON body of every AI request along with the current board state. Depending on KodeKloud's token limits, a very long conversation could cause provider errors that look like transient failures.

---

## Minor / Informational

- `hmac.new()` is functional but is the older module-level API. The more idiomatic modern form is `hmac.HMAC(key, msg, digestmod)`. No behaviour change.
- `session_max_age` is defined twice: once as `SESSION_MAX_AGE = 8 * 60 * 60` in `auth.py` and once inline as `8 * 60 * 60` in `create_app`'s default parameter. The constant is not imported at the call site.
- `backend/tests/test_board_api.py` inserts a hardcoded timestamp string `"2026-09-02T20:00:00+00:00"` intended to be a "past" anchor. This will behave unexpectedly if tests are run close to or after that date.
