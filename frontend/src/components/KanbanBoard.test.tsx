import type { ReactNode } from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DragEndEvent } from "@dnd-kit/core";
import { KanbanBoard } from "@/components/KanbanBoard";
import {
  ApiError,
  createCard,
  deleteCard,
  editCard,
  getBoard,
  moveCard as persistCardMove,
  renameColumn,
} from "@/lib/board-api";
import { initialData } from "@/test/fixtures";

const dndCapture = vi.hoisted(() => ({
  onDragEnd: undefined as ((event: DragEndEvent) => void) | undefined,
}));

vi.mock("@/lib/board-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/board-api")>();
  return {
    ...original,
    getBoard: vi.fn(),
    renameColumn: vi.fn(),
    createCard: vi.fn(),
    editCard: vi.fn(),
    deleteCard: vi.fn(),
    moveCard: vi.fn(),
  };
});

vi.mock("@dnd-kit/core", async (importOriginal) => {
  const original = await importOriginal<typeof import("@dnd-kit/core")>();
  return {
    ...original,
    DndContext: ({
      children,
      onDragEnd,
    }: {
      children: ReactNode;
      onDragEnd: (event: DragEndEvent) => void;
    }) => {
      dndCapture.onDragEnd = onDragEnd;
      return <>{children}</>;
    },
  };
});

const board = {
  id: "board-1",
  title: "Kanban Studio",
  ...initialData,
};

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.mocked(getBoard).mockResolvedValue(board);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("loads and renders five columns", async () => {
    render(<KanbanBoard />);
    expect(screen.getByText("Loading your board...")).toBeInTheDocument();
    await screen.findByText("Align roadmap themes");
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    vi.mocked(renameColumn).mockResolvedValue({
      ...board,
      columns: board.columns.map((column) =>
        column.id === "col-backlog" ? { ...column, title: "New Name" } : column
      ),
    });
    render(<KanbanBoard />);
    const column = await screen.findByTestId("column-col-backlog");
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    await userEvent.tab();
    await waitFor(() =>
      expect(renameColumn).toHaveBeenCalledWith("col-backlog", "New Name")
    );
  });

  it("adds and removes a card", async () => {
    const addedBoard = {
      ...board,
      cards: {
        ...board.cards,
        "card-new": { id: "card-new", title: "New card", details: "Notes" },
      },
      columns: board.columns.map((column) =>
        column.id === "col-backlog"
          ? { ...column, cardIds: [...column.cardIds, "card-new"] }
          : column
      ),
    };
    vi.mocked(createCard).mockResolvedValue(addedBoard);
    vi.mocked(deleteCard).mockResolvedValue(board);
    render(<KanbanBoard />);
    const column = await screen.findByTestId("column-col-backlog");
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await within(column).findByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    await waitFor(() =>
      expect(within(column).queryByText("New card")).not.toBeInTheDocument()
    );
  });

  it("edits a card", async () => {
    vi.mocked(editCard).mockResolvedValue({
      ...board,
      cards: {
        ...board.cards,
        "card-1": {
          ...board.cards["card-1"],
          title: "Updated roadmap",
          details: "Updated details",
        },
      },
    });
    render(<KanbanBoard />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit Align roadmap themes" })
    );
    const title = screen.getByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Updated roadmap");
    await userEvent.clear(screen.getByLabelText("Details"));
    await userEvent.type(screen.getByLabelText("Details"), "Updated details");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Updated roadmap")).toBeInTheDocument();
  });

  it("keeps the last valid board when a mutation fails", async () => {
    vi.mocked(renameColumn).mockRejectedValue(new ApiError(500));
    render(<KanbanBoard />);
    const column = await screen.findByTestId("column-col-backlog");
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Unsaved name");
    await userEvent.tab();

    expect(
      await screen.findByText("Your change could not be saved. Please try again.")
    ).toBeInTheDocument();
    await waitFor(() => expect(input).toHaveValue("Backlog"));
    expect(within(column).getByText("Align roadmap themes")).toBeInTheDocument();
  });

  it("reports an expired session", async () => {
    const onSessionExpired = vi.fn();
    vi.mocked(getBoard).mockRejectedValue(new ApiError(401));
    render(<KanbanBoard onSessionExpired={onSessionExpired} />);

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce());
  });

  it("optimistically moves a dragged card and persists the move", async () => {
    const movedBoard = {
      ...board,
      columns: board.columns.map((column) => {
        if (column.id === "col-backlog") {
          return {
            ...column,
            cardIds: column.cardIds.filter((id) => id !== "card-1"),
          };
        }
        if (column.id === "col-discovery") {
          return { ...column, cardIds: [...column.cardIds, "card-1"] };
        }
        return column;
      }),
    };
    vi.mocked(persistCardMove).mockResolvedValue(movedBoard);
    render(<KanbanBoard />);
    await screen.findByText("Align roadmap themes");

    await act(async () => {
      await dndCapture.onDragEnd?.({
        active: { id: "card-1" },
        over: { id: "col-discovery" },
      } as DragEndEvent);
    });

    expect(persistCardMove).toHaveBeenCalledWith("card-1", "col-discovery", 1);
    const discoveryColumn = await screen.findByTestId("column-col-discovery");
    expect(
      within(discoveryColumn).getByText("Align roadmap themes")
    ).toBeInTheDocument();
  });

  it("rolls back an optimistic card move when persisting fails", async () => {
    vi.mocked(persistCardMove).mockRejectedValue(new ApiError(500));
    render(<KanbanBoard />);
    await screen.findByText("Align roadmap themes");

    await act(async () => {
      await dndCapture.onDragEnd?.({
        active: { id: "card-1" },
        over: { id: "col-discovery" },
      } as DragEndEvent);
    });

    expect(
      await screen.findByText("Your change could not be saved. Please try again.")
    ).toBeInTheDocument();
    const backlogColumn = await screen.findByTestId("column-col-backlog");
    expect(
      within(backlogColumn).getByText("Align roadmap themes")
    ).toBeInTheDocument();
  });
});
