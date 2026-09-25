import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:8107/api/v1";
test("customer upload, manual bank verification, operator review and final delivery", async ({
  page,
  browser,
  request,
}) => {
  const email = `customer-${Date.now()}@example.test`;
  await page.goto("/register");
  await page.getByLabel(/name/i).first().fill("Browser Customer");
  await page.getByLabel(/email/i).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Customer-test-49283!");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("Customer-test-49283!");
  await page.getByRole("button", { name: /create|sign up|register/i }).click();
  await expect(page).toHaveURL(/\/orders$/);
  await page
    .getByRole("link", { name: "Digitize Questionnaire", exact: true })
    .click();
  await page.getByLabel("Job title").fill("Browser questionnaire");
  await page.getByLabel(/Questions, one per line/).fill("Department?");
  await page.getByRole("button", { name: /Create order and continue/ }).click();
  await expect(page).toHaveURL(/\/orders\/STF-/);
  const reference = page.url().split("/").pop()!;
  const root = `${api}/orders/${reference}/`;
  // A real PNG fixture; no OCR is simulated in manual transcription mode.
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "page.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAAHUlEQVR4nGP8//8/A7mAiWydo5pHNY9qHtVMFc0AnKADJXYG/XsAAAAASUVORK5CYII=",
        "base64",
      ),
    });
  await page.getByRole("button", { name: /Upload selected/ }).click();
  await page.getByRole("button", { name: /Validate uploads/ }).click();
  await expect(
    page.getByRole("heading", { name: "Bank transfer" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "I HAVE PAID", exact: true }).click();
  await expect(
    page.getByText(/payment claim is awaiting manual/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open Apps Script" }),
  ).toHaveCount(0);
  const operator = await browser.newContext();
  const adminPage = await operator.newPage();
  await adminPage.goto("http://127.0.0.1:3107/login");
  await adminPage.getByLabel(/email/i).fill("operator@example.test");
  await adminPage.getByLabel(/password/i).fill("E2E-Operator-43892!");
  await adminPage.getByRole("button", { name: /log in|sign in/i }).click();
  await expect(adminPage).toHaveURL(/\/orders$/);
  await adminPage.goto(`http://127.0.0.1:3107/orders/${reference}`);
  await adminPage
    .getByRole("button", { name: "VERIFY PAYMENT", exact: true })
    .click();
  await expect(
    adminPage.getByText("Payment: VERIFIED", { exact: true }),
  ).toBeVisible();
  const token = await adminPage.evaluate(() =>
    localStorage.getItem("scanforms_access"),
  );
  const headers = { Authorization: `Bearer ${token}` };
  async function post(path: string, data: unknown = {}) {
    const res = await request.post(path, { headers, data });
    expect(res.ok(), await res.text()).toBeTruthy();
    return res.json();
  }
  await post(root + "schema/", {
    questions: [
      {
        key: "q1",
        text: "Department?",
        position: 1,
        type: "SHORT_TEXT",
        required: true,
        template_page_number: 1,
        options: [],
      },
    ],
  });
  await post(root + "process/");
  const respondents = await (
    await request.get(root + "respondents/", { headers })
  ).json();
  const responseId = respondents.results[0].id;
  await adminPage.goto(
    `http://127.0.0.1:3107/dashboard/review/${responseId}?order=${reference}`,
  );
  await adminPage
    .getByRole("button", { name: /Record manual page inspection/ })
    .click();
  await adminPage
    .getByRole("button", { name: "Apply page correction" })
    .click();
  await expect(adminPage.getByText("Page assignment corrected and respondent answers re-aggregated.")).toBeVisible();
  await adminPage
    .getByPlaceholder("Enter or correct the answer")
    .fill("Engineering");
  await adminPage
    .getByRole("button", { name: /Approve all answers and confirm/ })
    .click();
  await expect(adminPage.getByText(/Respondent confirmed/)).toBeVisible();
  await post(root + "prepare-script/", {
    form_id: "1234567890abcdefghijklmnopqrstuvwxyz",
    mappings: { q1: "Department?" },
  });
  await post(root + "ready/");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your result is ready" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open Apps Script" }).click();
  await expect(page.getByLabel("Generated Apps Script")).toContainText(
    "Engineering",
  );
  await expect(page.getByText(/previewMapping/).first()).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download XLSX" }).click();
  const file = await downloadPromise;
  expect(file.suggestedFilename()).toBe(`${reference}.xlsx`);
  await page.getByRole("link", { name: /Notifications/ }).click();
  await expect(page.getByText(/ready/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await operator.close();
});
