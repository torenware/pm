import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { ApiError } from "@/lib/board-api";
import { sendAIMessage } from "@/lib/ai-api";
import { initialData } from "@/lib/kanban";

vi.mock("@/lib/ai-api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/ai-api")>();
  return { ...original, sendAIMessage: vi.fn() };
});

const board = {
  id: "board-1",
  title: "Kanban Studio",
  ...initialData,
};

describe("AIChatSidebar", () => {
  beforeEach(() => {
    vi.mocked(sendAIMessage).mockReset();
  });

  it("focuses the composer when opened and closes with Escape", async () => {
    render(<AIChatSidebar onBoardChange={vi.fn()} />);

    const trigger = screen.getByRole("button", { name: "Open AI assistant" });
    await userEvent.click(trigger);
    const input = screen.getByLabelText("Message the board assistant");
    expect(input).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("sends prior history, renders messages, and updates the board", async () => {
    const changedBoard = { ...board, title: "Updated board" };
    vi.mocked(sendAIMessage)
      .mockResolvedValueOnce({
        assistantText: "The board looks healthy.",
        appliedOperations: [],
        board,
      })
      .mockResolvedValueOnce({
        assistantText: "I updated it.",
        appliedOperations: [],
        board: changedBoard,
      });
    const onBoardChange = vi.fn();
    render(<AIChatSidebar onBoardChange={onBoardChange} />);

    const input = screen.getByLabelText("Message the board assistant");
    await userEvent.type(input, "How is the board?{enter}");
    expect(await screen.findByText("The board looks healthy.")).toBeInTheDocument();
    expect(sendAIMessage).toHaveBeenNthCalledWith(1, "How is the board?", []);

    await userEvent.type(input, "Update it{enter}");
    expect(await screen.findByText("I updated it.")).toBeInTheDocument();
    expect(sendAIMessage).toHaveBeenNthCalledWith(2, "Update it", [
      { role: "user", content: "How is the board?" },
      { role: "assistant", content: "The board looks healthy." },
    ]);
    expect(onBoardChange).toHaveBeenLastCalledWith(changedBoard);
  });

  it("shows a pending state and prevents duplicate submission", async () => {
    let resolveRequest!: (value: Awaited<ReturnType<typeof sendAIMessage>>) => void;
    vi.mocked(sendAIMessage).mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      })
    );
    render(<AIChatSidebar onBoardChange={vi.fn()} />);

    const input = screen.getByLabelText("Message the board assistant");
    await userEvent.type(input, "Plan the work{enter}");
    expect(screen.getByRole("status")).toHaveTextContent("Thinking...");
    expect(input).toBeDisabled();
    expect(sendAIMessage).toHaveBeenCalledOnce();

    resolveRequest({ assistantText: "Done", appliedOperations: [], board });
    expect(await screen.findByText("Done")).toBeInTheDocument();
  });

  it("retries without duplicating the failed user message", async () => {
    vi.mocked(sendAIMessage)
      .mockRejectedValueOnce(new ApiError(502))
      .mockResolvedValueOnce({
        assistantText: "Recovered.",
        appliedOperations: [],
        board,
      });
    render(<AIChatSidebar onBoardChange={vi.fn()} />);

    await userEvent.type(
      screen.getByLabelText("Message the board assistant"),
      "Move the card{enter}"
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The assistant could not respond"
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("Recovered.")).toBeInTheDocument();
    expect(screen.getAllByText("Move the card")).toHaveLength(1);
    expect(sendAIMessage).toHaveBeenNthCalledWith(2, "Move the card", []);
  });

  it("reports an expired session", async () => {
    vi.mocked(sendAIMessage).mockRejectedValue(new ApiError(401));
    const onSessionExpired = vi.fn();
    render(
      <AIChatSidebar
        onBoardChange={vi.fn()}
        onSessionExpired={onSessionExpired}
      />
    );

    await userEvent.type(
      screen.getByLabelText("Message the board assistant"),
      "Hello{enter}"
    );
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledOnce());
  });
});