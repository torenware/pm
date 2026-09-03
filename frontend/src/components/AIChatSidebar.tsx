"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, MessageSquare, RefreshCw, Send, X } from "lucide-react";
import { ApiError, type Board } from "@/lib/board-api";
import {
  sendAIMessage,
  type ChatMessage,
} from "@/lib/ai-api";

type AIChatSidebarProps = {
  onBoardChange: (board: Board) => void;
  onSessionExpired?: () => void;
};

type FailedRequest = {
  message: string;
  history: ChatMessage[];
};

const MAX_HISTORY_MESSAGES = 20;

export function AIChatSidebar({
  onBoardChange,
  onSessionExpired,
}: AIChatSidebarProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [failedRequest, setFailedRequest] = useState<FailedRequest | null>(null);
  const [open, setOpen] = useState(false);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages, pending]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function submitMessage(message: string, history: ChatMessage[]) {
    setPending(true);
    setError("");
    setFailedRequest(null);
    try {
      const result = await sendAIMessage(
        message,
        history.slice(-MAX_HISTORY_MESSAGES)
      );
      setMessages([
        ...history,
        { role: "user", content: message },
        { role: "assistant", content: result.assistantText },
      ]);
      onBoardChange(result.board);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        onSessionExpired?.();
        return;
      }
      setMessages([...history, { role: "user", content: message }]);
      setFailedRequest({ message, history });
      setError("The assistant could not respond. Please try again.");
    } finally {
      setPending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || pending) return;
    const history = messages;
    setInput("");
    setMessages([...history, { role: "user", content: message }]);
    void submitMessage(message, history);
  }

  function handleRetry() {
    if (!failedRequest || pending) return;
    setMessages(failedRequest.history);
    void submitMessage(failedRequest.message, failedRequest.history);
  }

  return (
    <>
      <button
        type="button"
        className="ai-chat-trigger"
        aria-label="Open AI assistant"
        aria-expanded={open}
        aria-controls="ai-chat-panel"
        onClick={() => setOpen(true)}
      >
        <MessageSquare aria-hidden="true" size={20} />
      </button>
      {open ? (
        <button
          type="button"
          className="ai-chat-scrim"
          aria-label="Close AI assistant"
          onClick={() => setOpen(false)}
        />
      ) : null}
      <aside
        id="ai-chat-panel"
        className={`ai-chat-panel ${open ? "is-open" : ""}`}
        aria-label="AI assistant"
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
      >
        <header className="ai-chat-header">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center bg-[var(--navy-dark)] text-white">
              <Bot aria-hidden="true" size={18} />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold text-[var(--navy-dark)]">
                Board assistant
              </h2>
              <p className="text-xs text-[var(--gray-text)]">Current session only</p>
            </div>
          </div>
          <button
            type="button"
            className="ai-icon-button ai-chat-close"
            aria-label="Close AI assistant"
            title="Close AI assistant"
            onClick={() => setOpen(false)}
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>

        <div className="ai-chat-messages" aria-live="polite">
          {messages.length === 0 ? (
            <div className="ai-chat-empty">
              <p className="font-display text-xl font-semibold text-[var(--navy-dark)]">
                What should move next?
              </p>
              <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
                Ask about the board or request card and column changes.
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`ai-message ai-message-${message.role}`}
              >
                <p className="ai-message-role">
                  {message.role === "user" ? "You" : "Assistant"}
                </p>
                <p className="whitespace-pre-wrap text-sm leading-6">
                  {message.content}
                </p>
              </div>
            ))
          )}
          {pending ? (
            <div className="ai-message ai-message-assistant" role="status">
              <p className="ai-message-role">Assistant</p>
              <p className="text-sm text-[var(--gray-text)]">Thinking...</p>
            </div>
          ) : null}
          {error ? (
            <div className="ai-chat-error" role="alert">
              <p>{error}</p>
              <button
                type="button"
                className="ai-retry-button"
                onClick={handleRetry}
                disabled={pending}
              >
                <RefreshCw aria-hidden="true" size={14} />
                Retry
              </button>
            </div>
          ) : null}
          <div ref={messageEndRef} />
        </div>

        <form className="ai-chat-composer" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="ai-chat-input">
            Message the board assistant
          </label>
          <textarea
            ref={inputRef}
            id="ai-chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask about your board..."
            rows={3}
            disabled={pending}
          />
          <button
            type="submit"
            className="ai-send-button"
            aria-label="Send message"
            title="Send message"
            disabled={pending || !input.trim()}
          >
            <Send aria-hidden="true" size={18} />
          </button>
        </form>
      </aside>
    </>
  );
}