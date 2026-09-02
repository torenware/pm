import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
}

test("loads the kanban board", async ({ page }) => {
  await signIn(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("persists board changes across reloads", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const secondColumn = page.locator('[data-testid^="column-"]').nth(1);
  const columnTitle = firstColumn.getByLabel("Column title");

  const currentBoard = (await (await page.request.get("/api/board")).json()) as {
    cards: Record<string, { id: string; title: string }>;
  };
  for (const staleCard of Object.values(currentBoard.cards).filter((card) =>
    /browser card/i.test(card.title)
  )) {
    await page.request.delete(`/api/cards/${staleCard.id}`);
  }
  await page.reload();

  await columnTitle.fill("Incoming work");
  await columnTitle.press("Enter");
  await expect(columnTitle).toHaveValue("Incoming work");

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Persistent browser card");
  await firstColumn.getByPlaceholder("Details").fill("Created via the UI.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  const card = firstColumn.locator("article").filter({
    hasText: "Persistent browser card",
  });
  await expect(card).toBeVisible();

  await card.getByRole("button", { name: /edit persistent browser card/i }).click();
  const editForm = page.locator("article form");
  await editForm.locator('input[name="title"]').fill("Edited browser card");
  await editForm.locator('textarea[name="details"]').fill("Edited and persisted.");
  await editForm.locator('button[type="submit"]').click();
  const editedCard = firstColumn.locator("article").filter({
    hasText: "Edited browser card",
  });
  await expect(editedCard).toBeVisible();

  await secondColumn.scrollIntoViewIfNeeded();
  const cardBox = await editedCard.boundingBox();
  const columnBox = await secondColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(secondColumn.getByText("Edited browser card")).toBeVisible();

  await page.reload();
  await expect(page.locator('[data-testid^="column-"]').first().getByLabel("Column title")).toHaveValue(
    "Incoming work"
  );
  const persistedCard = page
    .locator('[data-testid^="column-"]')
    .nth(1)
    .locator("article")
    .filter({ hasText: "Edited browser card" });
  await expect(persistedCard.getByText("Edited and persisted.")).toBeVisible();

  await persistedCard.getByRole("button", { name: /delete edited browser card/i }).click();
  await expect(page.getByText("Edited browser card")).toHaveCount(0);
  const restoredTitle = page.locator('[data-testid^="column-"]').first().getByLabel("Column title");
  await restoredTitle.fill("Backlog");
  await restoredTitle.press("Enter");
  await page.reload();
  await expect(page.getByText("Edited browser card")).toHaveCount(0);
  await expect(page.locator('[data-testid^="column-"]').first().getByLabel("Column title")).toHaveValue(
    "Backlog"
  );
});

test("rejects invalid credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByText("Invalid username or password")).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(0);
});

test("retains the session across refresh and logs out", async ({ page }) => {
  await signIn(page);

  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.getByText("Signed in as user")).toBeVisible();

  const storage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
  }));
  expect(storage).toEqual({ local: [], session: [] });

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("rejects protected API access without a session", async ({ request }) => {
  const response = await request.get("/api/protected");

  expect(response.status()).toBe(401);
});

test("shows text replies and applies AI board operations", async ({ page }) => {
  await signIn(page);
  const initialBoard = (await (await page.request.get("/api/board")).json()) as {
    id: string;
    title: string;
    columns: Array<{ id: string; title: string; cardIds: string[] }>;
    cards: Record<string, { id: string; title: string; details: string }>;
  };
  const responses = [
    { assistantText: "Your board has five stages.", board: initialBoard },
    {
      assistantText: "Created the launch card.",
      board: {
        ...initialBoard,
        cards: {
          ...initialBoard.cards,
          "ai-launch": {
            id: "ai-launch",
            title: "Launch checklist",
            details: "Prepare release notes.",
          },
        },
        columns: initialBoard.columns.map((column, index) =>
          index === 0
            ? { ...column, cardIds: [...column.cardIds, "ai-launch"] }
            : column
        ),
      },
    },
    {
      assistantText: "Updated the launch card.",
      board: {
        ...initialBoard,
        cards: {
          ...initialBoard.cards,
          "ai-launch": {
            id: "ai-launch",
            title: "Launch plan",
            details: "Release notes are ready.",
          },
        },
        columns: initialBoard.columns.map((column, index) =>
          index === 0
            ? { ...column, cardIds: [...column.cardIds, "ai-launch"] }
            : column
        ),
      },
    },
    {
      assistantText: "Moved the launch card.",
      board: {
        ...initialBoard,
        cards: {
          ...initialBoard.cards,
          "ai-launch": {
            id: "ai-launch",
            title: "Launch plan",
            details: "Release notes are ready.",
          },
        },
        columns: initialBoard.columns.map((column, index) => ({
          ...column,
          cardIds:
            index === 1
              ? [...column.cardIds, "ai-launch"]
              : column.cardIds.filter((cardId) => cardId !== "ai-launch"),
        })),
      },
    },
    {
      assistantText: "Added both follow-up cards.",
      board: {
        ...initialBoard,
        cards: {
          ...initialBoard.cards,
          "ai-launch": {
            id: "ai-launch",
            title: "Launch plan",
            details: "Release notes are ready.",
          },
          "ai-metrics": {
            id: "ai-metrics",
            title: "Review launch metrics",
            details: "",
          },
          "ai-retro": {
            id: "ai-retro",
            title: "Schedule retrospective",
            details: "",
          },
        },
        columns: initialBoard.columns.map((column, index) => ({
          ...column,
          cardIds:
            index === 1
              ? [...column.cardIds, "ai-launch"]
              : index === 0
                ? [...column.cardIds, "ai-metrics", "ai-retro"]
                : column.cardIds.filter((cardId) => cardId !== "ai-launch"),
        })),
      },
    },
  ];
  const requests: Array<{
    message: string;
    history: Array<{ role: string; content: string }>;
  }> = [];
  let responseIndex = 0;
  await page.route("**/api/ai/board", async (route) => {
    requests.push(route.request().postDataJSON());
    const response = responses[responseIndex++];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...response, appliedOperations: [] }),
    });
  });

  const composer = page.getByLabel("Message the board assistant");
  for (const message of [
    "Summarize the board",
    "Create a launch checklist",
    "Edit the launch card",
    "Move the launch card",
    "Add two follow-up cards",
  ]) {
    await composer.fill(message);
    await composer.press("Enter");
    await expect(page.getByText(responses[responseIndex - 1].assistantText)).toBeVisible();
  }

  await expect(page.getByText("Launch plan")).toBeVisible();
  await expect(
    page.locator('[data-testid^="column-"]').nth(1).getByText("Launch plan")
  ).toBeVisible();
  await expect(page.getByText("Review launch metrics")).toBeVisible();
  await expect(page.getByText("Schedule retrospective")).toBeVisible();
  expect(requests[1].history).toEqual([
    { role: "user", content: "Summarize the board" },
    { role: "assistant", content: "Your board has five stages." },
  ]);

  await page
    .getByTestId("card-ai-launch")
    .getByRole("button", { name: "Edit Launch plan", exact: true })
    .click();
  await expect(
    page.getByTestId("card-ai-launch").getByRole("button", { name: "Save", exact: true })
  ).toBeVisible();
});

test("clears chat on reload and logout", async ({ page }) => {
  await page.route("**/api/ai/board", async (route) => {
    const board = await (await page.request.get("/api/board")).json();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        assistantText: "Session-only response",
        appliedOperations: [],
        board,
      }),
    });
  });
  await signIn(page);
  const composer = page.getByLabel("Message the board assistant");
  await composer.fill("Remember this");
  await composer.press("Enter");
  await expect(page.getByText("Session-only response")).toBeVisible();

  await page.reload();
  await expect(page.getByText("Session-only response")).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page);
  await expect(page.getByText("Remember this")).toHaveCount(0);
});

test("opens the AI assistant without covering the mobile board", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);

  const trigger = page.getByRole("button", { name: "Open AI assistant" });
  await expect(trigger).toBeVisible();
  await trigger.click();
  await expect(page.getByLabel("Message the board assistant")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator('[data-testid^="column-"]').first()).toBeVisible();
});
