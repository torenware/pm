import { apiRequest, type Board } from "@/lib/board-api";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type BoardOperation =
  | {
      operationId: string;
      type: "create_card";
      columnId: string;
      title: string;
      details: string;
    }
  | {
      operationId: string;
      type: "edit_card";
      cardId: string;
      title: string;
      details: string;
    }
  | { operationId: string; type: "delete_card"; cardId: string }
  | {
      operationId: string;
      type: "move_card";
      cardId: string;
      columnId: string;
      position: number;
    }
  | {
      operationId: string;
      type: "rename_column";
      columnId: string;
      title: string;
    };

export type AIBoardResponse = {
  assistantText: string;
  appliedOperations: BoardOperation[];
  board: Board;
};

export function sendAIMessage(
  message: string,
  history: ChatMessage[]
): Promise<AIBoardResponse> {
  return apiRequest<AIBoardResponse>("/api/ai/board", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}