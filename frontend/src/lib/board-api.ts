import type { BoardData } from "@/lib/kanban";

export type Board = BoardData & {
  id: string;
  title: string;
};

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`Board request failed with status ${status}`);
  }
}

async function requestBoard(
  path: string,
  init?: RequestInit
): Promise<Board> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init?.headers,
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  return (await response.json()) as Board;
}

export const getBoard = () => requestBoard("/api/board");

export const renameColumn = (columnId: string, title: string) =>
  requestBoard(`/api/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const createCard = (
  columnId: string,
  title: string,
  details: string
) =>
  requestBoard("/api/cards", {
    method: "POST",
    body: JSON.stringify({ columnId, title, details }),
  });

export const editCard = (cardId: string, title: string, details: string) =>
  requestBoard(`/api/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ title, details }),
  });

export const deleteCard = (cardId: string) =>
  requestBoard(`/api/cards/${cardId}`, { method: "DELETE" });

export const moveCard = (cardId: string, columnId: string, position: number) =>
  requestBoard(`/api/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ columnId, position }),
  });