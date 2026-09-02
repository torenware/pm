# Frontend instructions

## Purpose

This directory contains the existing frontend-only Kanban demo. Preserve its behavior and visual language while incrementally connecting it to the FastAPI backend according to `docs/PLAN.md`.

## Current stack

- Next.js 16 App Router with React 19 and TypeScript.
- Tailwind CSS 4 through PostCSS.
- `@dnd-kit` for card drag and drop.
- Vitest, Testing Library, and jsdom for unit and component tests.
- Playwright for browser tests.
- ESLint with the Next.js configuration.

## Current structure

- `src/app/page.tsx` renders the authentication-gated application at `/`.
- `src/app/layout.tsx` defines the root document and fonts.
- `src/app/globals.css` contains global styles, theme variables, and Tailwind setup.
- `src/components/AuthGate.tsx` restores the backend session, handles login/logout, and gates board rendering.
- `src/components/KanbanBoard.tsx` loads the authenticated board, owns the rendered board state, and coordinates API-backed board actions.
- `src/components/AIChatSidebar.tsx` holds session-only chat history and applies AI responses to the visible board.
- `src/components/KanbanColumn.tsx` renders a sortable column and column controls.
- `src/components/KanbanCard.tsx` and `KanbanCardPreview.tsx` render cards and drag previews.
- `src/components/NewCardForm.tsx` handles card creation input.
- `src/lib/board-api.ts` defines the typed API boundary for board reads and mutations.
- `src/lib/ai-api.ts` defines the typed AI board-operation request boundary.
- `src/lib/kanban.ts` defines board types and pure optimistic card-move behavior.
- `src/lib/kanban.test.ts` tests pure board movement logic.
- `src/components/KanbanBoard.test.tsx` tests board component interactions.
- `tests/kanban.spec.ts` tests primary browser workflows.

## Existing behavior

- The board has five fixed columns whose titles can be renamed.
- Users can create, edit, and delete cards.
- Cards can be reordered and moved between columns with drag and drop.
- Board data is loaded from FastAPI and persisted in SQLite.
- Successful mutation responses replace local state with the canonical server board.
- Drag and drop updates optimistically and reverts to the last server board on failure.
- Authentication uses the backend's HTTP-only session cookie.
- AI chat is displayed as a desktop sidebar and a mobile drawer.
- Chat history remains in React memory, is sent with each AI request, and clears on reload or logout.
- Valid AI responses replace the visible board with the canonical board returned by FastAPI.

## Commands

- `npm run dev`: run the Next.js development server.
- `npm run build`: build the frontend.
- `npm run lint`: run ESLint.
- `npm run test:unit`: run Vitest once.
- `npm run test:e2e`: run Playwright tests.
- `npm run test:all`: run unit and browser tests.

## Coding guidelines

- Follow the approval gates in `docs/PLAN.md`; do not implement later parts early.
- Keep TypeScript types explicit at API and component boundaries.
- Keep pure board transformations in `src/lib/` and UI behavior in components.
- Preserve the fixed-column model; columns may be renamed but not created, deleted, or reordered.
- Preserve accessible names and stable `data-testid` values used by current tests unless tests and behavior intentionally change together.
- Use the existing project colors and responsive visual style rather than introducing a separate design system.
- Add focused Testing Library coverage for component behavior and Playwright coverage for complete user workflows.
- Configure production output as a static export when integrating with FastAPI; do not run a separate Next.js production server in the final container.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
