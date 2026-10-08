import { test, expect } from "@playwright/test";
test("admin can preview and publish an announcement", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin@example.test");
  await page.getByLabel("Password", { exact: true }).fill("E2E-Admin-43892!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/orders$/);
  await page.getByRole("link", { name: "Admin dashboard" }).click();
  await expect(
    page.getByRole("heading", { name: "A clear view of your operations." }),
  ).toBeVisible();
  await page.getByLabel("Title", { exact: true }).fill("Browser announcement");
  await page
    .getByLabel("Message", { exact: true })
    .fill("Your inbox is working.");
  await page.getByRole("button", { name: "Preview announcement" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Your inbox is working.",
  );
  await page.getByRole("button", { name: "Send announcement" }).click();
  await expect(page.getByRole("status")).toContainText("Announcement saved");
  await page.getByRole("link", { name: /^Notifications/ }).click();
  await expect(
    page.getByRole("heading", { name: "Browser announcement" }),
  ).toBeVisible();
});
test("mobile navigation and offline shell", async ({ page, context }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Email address").fill("operator@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("E2E-Operator-43892!");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/orders$/);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("link", { name: "Digitize Questionnaire", exact: true })
    .click();
  await expect(page).toHaveURL(/\/digitize$/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await context.setOffline(true);
  await page.goto("/orders");
  await expect(
    page.getByRole("heading", { name: "A little pause. Your work is safe." }),
  ).toBeVisible();
  const cached = await page.evaluate(async () => {
    const keys = await caches.keys();
    return (
      await Promise.all(
        keys.map(async (key) =>
          (await (await caches.open(key)).keys()).map(
            (req) => new URL(req.url).pathname,
          ),
        ),
      )
    ).flat();
  });
  expect(cached).toContain("/offline.html");
  expect(
    cached.some(
      (path) =>
        path.includes("/api/") || path === "/orders" || path === "/login",
    ),
  ).toBeFalsy();
  await context.setOffline(false);
});
