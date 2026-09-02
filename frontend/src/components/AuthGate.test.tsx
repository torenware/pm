import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";

const response = (ok: boolean, body: object = {}) =>
  Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);

describe("AuthGate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the login form when there is no active session", async () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(response(false));

    render(<AuthGate />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Kanban Studio" })).not.toBeInTheDocument();
  });

  it("submits credentials and renders the board", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValueOnce(response(false))
      .mockReturnValueOnce(response(true, { username: "user" }));
    const user = userEvent.setup();

    render(<AuthGate />);
    await user.type(await screen.findByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "user", password: "password" }),
      })
    );
  });

  it("shows invalid credential errors without exposing the board", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockReturnValueOnce(response(false))
      .mockReturnValueOnce(response(false));
    const user = userEvent.setup();

    render(<AuthGate />);
    await user.type(await screen.findByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password"
    );
    expect(screen.queryByTestId("column-col-backlog")).not.toBeInTheDocument();
  });

  it("restores an active session and logs out", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValueOnce(response(true, { username: "user" }))
      .mockReturnValueOnce(response(true));
    const user = userEvent.setup();

    render(<AuthGate />);
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
    });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/logout", { method: "POST" });
  });
});