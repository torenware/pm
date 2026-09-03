import {
  ApiError,
  createCard,
  deleteCard,
  editCard,
  getBoard,
  moveCard,
  renameColumn,
} from "@/lib/board-api";
import { initialData } from "@/test/fixtures";

const board = { id: "board-1", title: "Kanban Studio", ...initialData };
const response = (ok = true, status = 200) =>
  Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(board),
  } as Response);

describe("board API", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads the authenticated board", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockReturnValue(response());
    await expect(getBoard()).resolves.toEqual(board);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/board");
    expect(init?.body).toBeUndefined();
  });

  it.each([
    [
      () => renameColumn("col-1", "Ideas"),
      "/api/columns/col-1",
      "PATCH",
      { title: "Ideas" },
    ],
    [
      () => createCard("col-1", "New card", "Details"),
      "/api/cards",
      "POST",
      { columnId: "col-1", title: "New card", details: "Details" },
    ],
    [
      () => editCard("card-1", "Edited", "New details"),
      "/api/cards/card-1",
      "PATCH",
      { title: "Edited", details: "New details" },
    ],
    [
      () => moveCard("card-1", "col-2", 0),
      "/api/cards/card-1/move",
      "POST",
      { columnId: "col-2", position: 0 },
    ],
  ])("sends a board mutation", async (operation, path, method, body) => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockReturnValue(response());
    await operation();
    expect(fetchMock).toHaveBeenCalledWith(path, {
      method,
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    });
  });

  it("deletes a card", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockReturnValue(response());
    await deleteCard("card-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/cards/card-1");
    expect(init?.method).toBe("DELETE");
    expect(init?.body).toBeUndefined();
  });

  it("exposes the response status for error handling", async () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(response(false, 401));
    await expect(getBoard()).rejects.toEqual(new ApiError(401));
  });
});