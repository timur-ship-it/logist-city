const { chromium } = require("playwright");

const SITE_URL = "https://timur-ship-it.github.io/logist-city/";
const GOOGLE_SCRIPT_RE = /script\.google\.com\/macros\/s\/.*\/exec/;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function setCompanyFields(page) {
  await page.fill("#companyName", "AUTO QA LLC");
  await page.fill("#contactPerson", "Auto Tester");
  await page.fill("#contactEmail", "auto@test.local");
}

async function getToast(page) {
  return page.locator("#toast").innerText().catch(() => "");
}

async function waitToastContains(page, text, timeoutMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const msg = await getToast(page);
    if (msg && msg.includes(text)) return true;
    await sleep(100);
  }
  return false;
}

async function waitRequiredValidation(page, timeoutMs = 7000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const msg = await getToast(page);
    if (msg && (msg.includes("типоразмер") || msg.includes("обязательные параметры"))) {
      return true;
    }
    const cartWarningCount = await page.locator(".cart-warning").count();
    if (cartWarningCount > 0) return true;
    await sleep(100);
  }
  return false;
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.route(GOOGLE_SCRIPT_RE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, reqId: `AUTO-${Date.now()}` }),
    });
  });

  await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForSelector("#companyName", { timeout: 15000 });

  const requiredIds = await page.evaluate(() => {
    if (typeof ABRASIVE_SIZE_OPTIONS !== "object" || !ABRASIVE_SIZE_OPTIONS) return [];
    return Object.keys(ABRASIVE_SIZE_OPTIONS).filter((id) => {
      const card = document.querySelector(`.product[data-id="${id}"]`);
      if (!card) return false;
      if (card.dataset.removed === "true") return false;
      const sizeSel = card.querySelector(`select[data-size="${id}"]`);
      const qtyInput = card.querySelector(`.qty-input[data-qty="${id}"]`);
      return !!sizeSel && !!qtyInput;
    });
  });

  const results = [];
  let skipped = 0;

  for (const id of requiredIds) {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector("#companyName");
    await setCompanyFields(page);

    const exists = await page.locator(`.product[data-id="${id}"]`).count();
    if (!exists) {
      results.push({ id, status: "FAIL", reason: "card not found" });
      continue;
    }

    const hasEmptyOption = await page.evaluate((pid) => {
      const sel = document.querySelector(`.product[data-id="${pid}"] select[data-size="${pid}"]`);
      if (!sel) return false;
      return Array.from(sel.options).some((o) => o.value === "");
    }, id);

    if (!hasEmptyOption) {
      skipped += 1;
      continue;
    }

    await page.selectOption(`.product[data-id="${id}"] select[data-size="${id}"]`, "");
    await page.fill(`.product[data-id="${id}"] .qty-input[data-qty="${id}"]`, "1");
    await page.click("#submitBtn");

    const blocked = await waitRequiredValidation(page, 7000);
    const cartOpened = await page.evaluate(() => {
      const drawer = document.getElementById("cartDrawer");
      return !!drawer && drawer.classList.contains("open");
    });
    if (blocked && cartOpened) {
      results.push({ id, status: "PASS" });
    } else if (blocked && !cartOpened) {
      results.push({ id, status: "FAIL", reason: "size toast shown but cart did not open" });
    } else {
      results.push({ id, status: "FAIL", reason: "no typorazmer block toast" });
    }
  }

  const pass = results.filter((r) => r.status === "PASS").length;
  const fail = results.filter((r) => r.status === "FAIL").length;
  const failedIds = results.filter((r) => r.status === "FAIL").map((r) => `${r.id}:${r.reason}`);

  console.log(`TOTAL_REQUIRED_IDS: ${requiredIds.length}`);
  console.log(`TESTED_WITH_EMPTY_OPTION: ${results.length}`);
  console.log(`SKIPPED_NO_EMPTY_OPTION: ${skipped}`);
  console.log(`PASS: ${pass}`);
  console.log(`FAIL: ${fail}`);
  if (failedIds.length) {
    console.log(`FAILED_IDS: ${failedIds.join(",")}`);
  }

  await browser.close();
  process.exit(fail > 0 ? 1 : 0);
}

run().catch((err) => {
  console.error(`FATAL: ${err.message}`);
  process.exit(1);
});
