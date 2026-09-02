# Project Management MVP Plan

## Confirmed decisions

- Each numbered part is a separate approval gate. Work on the next part starts only after the user approves the current part.
- The application runs locally as one Docker Compose service.
- FastAPI serves both the API and the statically exported Next.js application.
- SQLite data persists between container sessions in the repository-local `data/` directory, bind-mounted at `/data` in the container.
- Authentication uses the fixed credentials `user` and `password`, with a backend-managed session cookie.
- The database schema supports multiple users, while the MVP gives each user one board.
- AI conversation history is held in browser memory and is not stored in SQLite.
- AI board changes use explicit, validated operations rather than replacing the complete board.
- The KodeKloud API uses `gpt-oss-120b`, `KK_API_KEY`, and `KK_BASE_URL`.
- macOS and Linux use shell scripts; Windows uses PowerShell scripts.

## Rules for every part

- [x] Keep changes limited to the current approved part.
- [x] Add or update tests for behavior introduced in the part.
- [x] Run the focused tests, then the relevant full test suite.
- [x] Update concise documentation when commands, architecture, or behavior change.
- [x] Record completed checklist items in this document.
- [ ] Present test results and request approval before starting the next part.

## Part 1: Plan

### Implementation checklist

- [x] Read the root project instructions and initial plan.
- [x] Resolve architecture and scope questions with the user.
- [x] Define detailed implementation steps, tests, and success criteria for all parts.
- [x] Create `frontend/AGENTS.md` describing the existing frontend.
- [x] Review this plan with the user and incorporate requested changes.
- [x] Receive explicit approval to begin Part 2.

### Tests

- [x] Verify that all ten parts have implementation checklists, tests, success criteria, and approval gates.
- [x] Verify that the confirmed decisions match the root project instructions and user answers.
- [x] Verify that `frontend/AGENTS.md` matches the current frontend code and commands.

### Success criteria

- The implementation can proceed one independently reviewable part at a time.
- Authentication, persistence, AI mutation, platform scripts, and container decisions are unambiguous.
- The user explicitly approves the plan.

### Approval gate

- [x] User approval received for Part 1.

## Part 2: Scaffolding

### Implementation checklist

- [x] Create a minimal FastAPI project in `backend/` managed by `uv`.
- [x] Add a health API endpoint that returns a small JSON response.
- [x] Serve a minimal static HTML page at `/` that calls and displays the health endpoint response.
- [x] Add a production Dockerfile that installs Python dependencies with `uv` and runs FastAPI.
- [x] Add `compose.yaml` with one application service, environment loading, port mapping, and a local data mount.
- [x] Mount the repository-local `data/` directory at a stable application data path reserved for SQLite.
- [x] Add start and stop shell scripts for macOS and Linux.
- [x] Add start and stop PowerShell scripts for Windows.
- [x] Update `backend/AGENTS.md` and `scripts/AGENTS.md` to describe their implemented contents.
- [x] Document only the commands needed to configure and run the scaffold.

### Tests

- [x] Add a backend test for the health endpoint.
- [x] Build the image with Docker Compose.
- [x] Start the service and verify `/` returns the static page.
- [x] Verify the page successfully calls the health endpoint.
- [x] Run the applicable start and stop scripts on macOS; review Linux and PowerShell scripts for equivalent Compose behavior.

### Success criteria

- `docker compose up --build` starts one container without manual setup beyond the root `.env` file.
- The browser displays the example page and a successful API response.
- Data written under the mounted data path remains after the service is stopped and recreated.
- Platform scripts provide simple start and stop entry points.

### Approval gate

- [x] Present the running scaffold and test results.
- [x] User approval received for Part 2.

## Part 3: Add the frontend

### Implementation checklist

- [x] Configure Next.js for a static export compatible with FastAPI static hosting.
- [x] Add a frontend build stage to the Dockerfile.
- [x] Copy the exported frontend into the FastAPI static directory in the final image.
- [x] Replace the example page at `/` with the existing Kanban application.
- [x] Preserve column rename, card creation and deletion, and drag-and-drop behavior.
- [x] Keep frontend state local and non-persistent during this part.
- [x] Ensure static asset and client-side route requests are served correctly by FastAPI.
- [x] Document frontend build and test commands.

### Tests

- [x] Run frontend unit tests and linting.
- [x] Run the existing Playwright tests against the container-served application.
- [x] Add an integration test proving FastAPI serves the exported index and static assets.
- [x] Verify a production Docker Compose build contains no Next.js development server.

### Success criteria

- The existing Kanban board loads at `/` from the FastAPI container.
- Existing frontend interactions continue to work.
- The browser has no missing asset or runtime errors.
- Unit, integration, and end-to-end tests pass.

### Approval gate

- [x] Present the container-served frontend and test results.
- [x] User approval received for Part 3.

## Part 4: Dummy user sign-in

### Implementation checklist

- [x] Add backend login, logout, and current-session endpoints.
- [x] Validate only the fixed MVP credentials `user` and `password`.
- [x] Create a signed, HTTP-only session cookie on successful login.
- [x] Configure appropriate local cookie settings, expiry, and logout invalidation.
- [x] Protect authenticated API routes with one reusable FastAPI dependency.
- [x] Add a frontend login screen shown when no valid session exists.
- [x] Add logout control and return the user to the login screen after logout.
- [x] Handle invalid credentials and expired sessions without exposing protected content.
- [x] Keep credentials and session identifiers out of browser storage.

### Tests

- [x] Add backend tests for successful login, rejected credentials, session lookup, protected access, logout, and expired or invalid cookies.
- [x] Add frontend tests for login form behavior, error display, authenticated rendering, and logout.
- [x] Add Playwright coverage for login, page refresh with an active session, failed login, and logout.

### Success criteria

- Unauthenticated users cannot view the board or call protected endpoints.
- `user` and `password` establish a backend session through an HTTP-only cookie.
- Refreshing the page retains the session until logout or expiry.
- Logout invalidates access on both frontend and backend.

### Approval gate

- [x] Demonstrate the sign-in lifecycle and present test results.
- [x] User approval received for Part 4.

## Part 5: Database modeling

### Implementation checklist

- [x] Propose a normalized SQLite schema for users, boards, columns, cards, and backend sessions.
- [x] Include stable identifiers, ownership relationships, ordering fields, timestamps where needed, and integrity constraints.
- [x] Keep the schema compatible with multiple users and one board per user.
- [x] Define how the fixed five columns are created and how their names and order are stored.
- [x] Define card ordering within columns and transactional move behavior.
- [x] Define session storage and expiry behavior.
- [x] Save the proposed schema as JSON under `docs/`.
- [x] Document migration and automatic database creation strategy under `docs/`.
- [x] Document the local data path, backup boundary, and reset procedure.
- [x] Review the schema with the user before writing database code.

### Tests

- [x] Validate that the schema JSON is syntactically valid.
- [x] Walk through sample records for one user, one board, five columns, cards, and a session.
- [x] Verify ownership, ordering, uniqueness, and foreign-key constraints cover required operations.
- [x] Verify the design supports atomic card moves and column renames.

### Success criteria

- The documented schema represents every required MVP entity and relationship.
- Board data cannot cross user ownership boundaries.
- Ordering and card moves do not rely on array blobs or full-board replacement.
- The user explicitly approves the schema and database approach.

### Approval gate

- [x] User approval received for Part 5 schema and persistence design.

## Part 6: Backend board API

### Implementation checklist

- [x] Add SQLite access using the approved schema and the standard library or one small established dependency.
- [x] Enable foreign-key enforcement and create or migrate the database at application startup.
- [x] Seed the fixed MVP user and that user's initial board only when absent.
- [x] Store the database in the repository-local data path.
- [x] Add authenticated endpoints to read the current user's board.
- [x] Add authenticated endpoints to rename a column and create, edit, delete, and move a card.
- [x] Validate ownership and request data at the API boundary.
- [x] Apply ordering changes and moves in transactions.
- [x] Return stable response models and appropriate HTTP errors.

### Tests

- [x] Add isolated backend tests using a temporary SQLite database.
- [x] Test first-run database creation and idempotent startup seeding.
- [x] Test board reads and every board mutation, including card editing.
- [x] Test same-column reorder and cross-column moves at the start, middle, and end.
- [x] Test validation failures, unknown identifiers, unauthenticated requests, and cross-user access.
- [x] Test transaction rollback for an invalid move.
- [x] Recreate the Compose service and verify persisted board data remains.

### Success criteria

- Every manual board action has an authenticated API operation.
- The API returns only the signed-in user's board.
- Database initialization is automatic and repeatable.
- Mutations preserve valid ordering and survive container recreation.
- Backend tests pass against SQLite rather than mocks of persistence behavior.

### Approval gate

- [x] Present API behavior, persistence proof, and test results.
- [x] User approval received for Part 6.

## Part 7: Connect frontend and backend

### Implementation checklist

- [x] Replace initial in-memory board data with an authenticated API fetch.
- [x] Connect column rename and card create, edit, delete, reorder, and move actions to backend endpoints.
- [x] Add the missing card edit interaction to the existing frontend.
- [x] Update local UI state from successful API responses.
- [x] Show focused loading and error states without discarding the last valid board.
- [x] Reconcile or revert optimistic drag state when a request fails.
- [x] Redirect to login when the backend reports an expired session.
- [x] Keep API access in a small typed frontend module.

### Tests

- [x] Add frontend unit tests for loading, successful mutations, failed mutations, and session expiry.
- [x] Add backend/frontend integration coverage for the board contract.
- [x] Extend Playwright tests to cover persisted rename, create, edit, delete, and move actions after page reload.
- [x] Verify data remains after stopping and recreating the container.
- [x] Run backend tests, frontend tests, linting, and Playwright tests.

Persistence across forced container recreation was verified manually by the user. The
automated Playwright suite passes, but an additional proof attempted through the shared
browser automation session was unreliable because that session timed out on otherwise
working UI actions. This browser-tool limitation does not invalidate the successful
manual persistence result.

### Success criteria

- The board shown in the UI is sourced from SQLite through FastAPI.
- Every supported UI mutation persists and remains after reload and container recreation.
- Failed mutations leave the UI consistent with the server.
- Authentication remains enforced for all board data.

### Approval gate

- [x] Demonstrate the persistent end-to-end board and present test results.
- [x] User approval received for Part 7.

## Part 8: AI connectivity

### Implementation checklist

- [x] Add a small backend KodeKloud client using `KK_BASE_URL`, `KK_API_KEY`, and `gpt-oss-120b`.
- [x] Keep secrets server-side and out of images, logs, responses, and frontend bundles.
- [x] Add an authenticated diagnostic endpoint or script that asks the model `2+2`.
- [x] Add clear timeout and provider error handling.
- [x] Document how to run the connectivity check without documenting secret values.

### Tests

- [x] Unit-test request construction, model selection, response parsing, timeout handling, and provider errors with a mocked HTTP boundary.
- [x] Run the live `2+2` connectivity check using the root `.env` values.
- [x] Verify that the returned answer is correct and no secret is exposed.

### Success criteria

- The backend successfully calls the configured KodeKloud model from the container.
- The connectivity check returns `4` or an equivalent correct answer.
- Provider failures produce controlled API errors.
- Credentials never reach the browser.

### Approval gate

- [x] Present the live connectivity result and automated test results.
- [x] User approval received for Part 8.

## Part 9: AI board operations

### Implementation checklist

- [x] Define a structured AI response containing assistant text and zero or more explicit board operations.
- [x] Support only required operations: create card, edit card, delete card, move card, and rename column.
- [x] Include operation identifiers and required arguments in a strict discriminated schema.
- [x] Send the current authenticated user's board, current user message, and browser-supplied conversation history to the model.
- [x] Do not write conversation history to SQLite or server-side session storage.
- [x] Instruct the model to reference existing board identifiers and return only supported operations.
- [x] Validate structured output before changing the database.
- [x] Validate every operation against board ownership and current state.
- [x] Apply all operations from one AI response in a single transaction, rolling back the whole set if any operation is invalid.
- [x] Return assistant text, applied operations, and the resulting board.

### Tests

- [x] Unit-test the structured response schema and each operation type.
- [x] Test malformed output, unsupported operations, missing identifiers, stale identifiers, and cross-user identifiers.
- [x] Test single and multiple valid operations.
- [x] Test that one invalid operation rolls back a multi-operation response.
- [x] Test prompt construction includes board state, the user message, and supplied history.
- [x] Test that conversation messages are absent from SQLite after AI calls.
- [x] Run controlled live prompts that create, edit, move, and rename board items.

### Success criteria

- AI responses always conform to the structured schema before use.
- The model can propose one or more explicit operations without replacing the full board.
- Only validated operations can mutate the signed-in user's board.
- Multi-operation changes are atomic.
- Conversation history is not persisted by the backend.

### Approval gate

- [x] Present structured operation examples, rollback behavior, and test results.
- [ ] User approval received for Part 9.

## Part 10: AI chat sidebar

### Implementation checklist

- [ ] Add a responsive AI chat sidebar integrated with the existing Kanban layout and project color scheme.
- [ ] Provide message history, message input, send action, pending state, error state, and retry behavior.
- [ ] Keep conversation history in React memory only and send it with each AI request.
- [ ] Clear chat history on logout and naturally lose it on reload or tab close.
- [ ] Render assistant text distinctly from user messages.
- [ ] Refresh the board from the AI response or a follow-up board fetch whenever operations are applied.
- [ ] Preserve manual board interactions while the chat is open.
- [ ] Make the sidebar usable on desktop and mobile without overlapping board controls or content.
- [ ] Add accessible labels, focus behavior, and keyboard submission.
- [ ] Keep secrets and raw model payloads out of the browser.

### Tests

- [ ] Add frontend tests for sending messages, rendering replies, pending state, errors, retry, and operation-triggered board refresh.
- [ ] Test that chat history is supplied on later turns but disappears after reload and logout.
- [ ] Add Playwright flows for a text-only reply and AI-driven create, edit, move, and multi-card updates.
- [ ] Verify manual drag-and-drop and edits still work with the sidebar open.
- [ ] Verify desktop and mobile layouts with Playwright screenshots and interaction checks.
- [ ] Run all backend, frontend, lint, integration, and end-to-end suites in the final container.

### Success criteria

- Users can hold a multi-turn AI conversation during the current browser session.
- Valid AI operations update SQLite and the visible board automatically.
- Chat history is never persisted and is cleared on reload or logout.
- The sidebar is accessible, responsive, and does not regress Kanban behavior.
- The complete application runs locally through the documented Docker Compose workflow.

### Approval gate

- [ ] Demonstrate the complete MVP and present the full test results.
- [ ] User approval received for Part 10 and project completion.