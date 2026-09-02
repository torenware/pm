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
