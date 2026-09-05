"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  pointerWithin,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import {
  createCard,
  deleteCard,
  editCard,
  getBoard,
  isSessionExpiredError,
  moveCard as persistCardMove,
  renameColumn,
  type Board,
} from "@/lib/board-api";
import { moveCard } from "@/lib/kanban";

type KanbanBoardProps = {
  username?: string;
  onLogout?: () => void;
  onSessionExpired?: () => void;
};

export const KanbanBoard = ({
  username,
  onLogout,
  onSessionExpired,
}: KanbanBoardProps) => {
  const [board, setBoard] = useState<Board | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleRequestError = (
    requestError: unknown,
    message = "Your change could not be saved. Please try again."
  ) => {
    if (isSessionExpiredError(requestError)) {
      onSessionExpired?.();
      return;
    }
    setError(message);
  };

  const runMutation = async (
    action: () => Promise<Board>,
    onFail?: () => void
  ): Promise<boolean> => {
    setError("");
    setSaving(true);
    try {
      setBoard(await action());
      return true;
    } catch (requestError) {
      onFail?.();
      handleRequestError(requestError);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const loadBoard = async () => {
    setError("");
    setLoading(true);
    try {
      setBoard(await getBoard());
    } catch (requestError) {
      handleRequestError(
        requestError,
        "Your board could not be loaded. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBoard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board?.cards ?? {}, [board?.cards]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const previousBoard = board;
    const columns = moveCard(
      board.columns,
      active.id as string,
      over.id as string
    );
    const targetColumn = columns.find((column) =>
      column.cardIds.includes(active.id as string)
    );
    if (!targetColumn) return;

    setBoard({ ...board, columns });
    await runMutation(
      () =>
        persistCardMove(
          active.id as string,
          targetColumn.id,
          targetColumn.cardIds.indexOf(active.id as string)
        ),
      () => setBoard(previousBoard)
    );
  };

  const handleRenameColumn = (columnId: string, title: string) =>
    runMutation(() => renameColumn(columnId, title));

  const handleAddCard = (columnId: string, title: string, details: string) =>
    runMutation(() => createCard(columnId, title, details));

  const handleEditCard = (cardId: string, title: string, details: string) =>
    runMutation(() => editCard(cardId, title, details));

  const handleDeleteCard = (cardId: string) =>
    runMutation(() => deleteCard(cardId));

  if (loading && !board) {
    return (
      <main className="grid min-h-screen place-items-center" aria-busy="true">
        <p className="text-sm font-semibold text-[var(--gray-text)]">
          Loading your board...
        </p>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="text-center">
          <p role="alert" className="text-sm font-semibold text-red-700">
            Your board could not be loaded.
          </p>
          <button
            type="button"
            className="mt-4 text-sm font-semibold text-[var(--secondary-purple)]"
            onClick={() => void loadBoard()}
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="kanban-shell" aria-busy={saving}>
        <div className="flex min-w-0 flex-col gap-10">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex items-center gap-5 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  {username ? `Signed in as ${username}` : "Focus"}
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              {onLogout ? (
                <button
                  type="button"
                  onClick={onLogout}
                  className="border-l border-[var(--stroke)] pl-5 text-sm font-semibold text-[var(--secondary-purple)] hover:text-[var(--navy-dark)]"
                >
                  Sign out
                </button>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
          {error ? (
            <p role="alert" className="text-sm font-semibold text-red-700">
              {error}
            </p>
          ) : null}
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={pointerWithin}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="grid grid-cols-[repeat(5,minmax(240px,1fr))] gap-6 overflow-x-auto pb-4">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds.map((cardId) => board.cards[cardId])}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onEditCard={handleEditCard}
                onDeleteCard={handleDeleteCard}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
        </div>
        <AIChatSidebar
          onBoardChange={setBoard}
          onSessionExpired={onSessionExpired}
        />
      </main>
    </div>
  );
};
