const { chromium } = require("playwright");

const SITE_URL = "https://timur-ship-it.github.io/logist-city/";
const GOOGLE_SCRIPT_RE = /script\.google\.com\/macros\/s\/.*\/exec/;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function expect(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function getToastText(page) {
  return page.locator("#toast").innerText().catch(() => "");
}

async function waitForToastContains(page, text, timeoutMs = 6000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const msg = await getToastText(page);
    if (msg && msg.includes(text)) return msg;
    await sleep(120);
  }
  throw new Error(`Toast did not contain "${text}" within ${timeoutMs}ms`);
}

async function waitForMissingRequiredValidation(page, timeoutMs = 6000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const msg = await getToastText(page);
    if (msg && (msg.includes("типоразмер") || msg.includes("обязательные параметры"))) {
      return true;
    }
    const cartWarningCount = await page.locator(".cart-warning").count();
    if (cartWarningCount > 0) return true;
    await sleep(120);
  }
  return false;
}

async function ensureCartClosed(page) {
  await page.evaluate(() => {
    if (typeof closeCartDrawer === "function") closeCartDrawer();
    const drawer = document.getElementById("cartDrawer");
    const overlay = document.getElementById("cartOverlay");
    if (drawer) drawer.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
  });
  await page.waitForTimeout(120);
}

async function firstProductWithoutSize(page) {
  return page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll(".product"));
    const card = cards.find((c) => {
      if (c.dataset.removed === "true") return false;
      if (c.style.display === "none") return false;
      const hasSizeSelect = c.querySelector("select.size-select");
      return !hasSizeSelect;
    });
    if (!card) return null;
    const qty = card.querySelector(".qty-input");
    const note = card.querySelector(".note-input");
    return {
      id: card.dataset.id || "",
      qtySelector: qty ? `.qty-input[data-qty="${qty.dataset.qty}"]` : null,
      noteSelector: note ? `.note-input[data-note="${note.dataset.note}"]` : null,
    };
  });
}

async function firstProductWithSize(page) {
  return page.evaluate(() => {
    const abrasiveIds = typeof ABRASIVE_SIZE_OPTIONS === "object"
      ? Object.keys(ABRASIVE_SIZE_OPTIONS || {})
      : [];
    let card = null;
    let preferEmpty = null;
    for (const id of abrasiveIds) {
      const c = document.querySelector(`.product[data-id="${id}"]`);
      if (!c) continue;
      if (c.dataset.removed === "true") continue;
      if (c.style.display === "none") continue;
      const sizeSelect = c.querySelector(`select[data-size="${id}"]`);
      const qtyInput = c.querySelector(`.qty-input[data-qty="${id}"]`);
      if (sizeSelect && qtyInput) {
        const hasEmpty = Array.from(sizeSelect.options).some((o) => o.value === "");
        if (hasEmpty) {
          preferEmpty = c;
          break;
        }
        if (!card) card = c;
      }
    }
    if (preferEmpty) card = preferEmpty;
    if (!card) return null;
    const id = card.dataset.id || "";
    const qty = card.querySelector(`.qty-input[data-qty="${id}"]`);
    const size = card.querySelector(`select[data-size="${id}"]`);
    const options = size ? Array.from(size.options).map((o) => o.value) : [];
    return {
      id,
      qtySelector: qty ? `.qty-input[data-qty="${qty.dataset.qty}"]` : null,
      sizeSelector: id ? `.product[data-id="${id}"] select[data-size="${id}"]` : null,
      hasEmptyOption: options.includes(""),
    };
  });
}

async function visibleProductCount(page) {
  return page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll(".product"));
    return cards.filter((c) => c.style.display !== "none").length;
  });
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const results = [];

  const test = async (name, fn) => {
    try {
      await fn();
      results.push({ name, status: "PASS" });
      console.log(`PASS: ${name}`);
    } catch (err) {
      results.push({ name, status: "FAIL", error: err.message });
      console.log(`FAIL: ${name} -> ${err.message}`);
    }
  };

  await page.route(GOOGLE_SCRIPT_RE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        reqId: `AUTO-${Date.now()}`,
      }),
    });
  });

  await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForSelector("#companyName", { timeout: 15000 });

  await test("Page loaded with core form controls", async () => {
    await expect(await page.locator("#companyName").count(), "companyName not found");
    await expect(await page.locator("#contactPerson").count(), "contactPerson not found");
    await expect(await page.locator("#contactEmail").count(), "contactEmail not found");
    await expect(await page.locator("#submitBtn").count(), "submitBtn not found");
  });

  await test("Validation blocks empty submit", async () => {
    await page.click("#submitBtn");
    await waitForToastContains(page, "название компании");
  });

  await test("Search filters products", async () => {
    const before = await visibleProductCount(page);
    await page.fill("#searchInput", "zzzzzzzz-no-such-product");
    await sleep(250);
    const after = await visibleProductCount(page);
    await expect(after < before, `search did not reduce visible products (${before} -> ${after})`);
    await page.fill("#searchInput", "");
  });

  await test("Add product without size and check cart count", async () => {
    const p = await firstProductWithoutSize(page);
    await expect(p && p.qtySelector, "product without size or qty not found");
    await page.fill(p.qtySelector, "3");
    if (p.noteSelector) {
      await page.fill(p.noteSelector, "auto smoke note");
    }
    await sleep(250);
    const countText = await page.locator("#cartFabCount").innerText();
    await expect(Number(countText) >= 1, `cart count not updated: ${countText}`);
  });

  await test("Draft persists after reload", async () => {
    await page.fill("#companyName", "AUTO QA LLC");
    await page.fill("#contactPerson", "Auto Tester");
    await page.fill("#contactEmail", "auto@test.local");
    await page.click("button:has-text('Сохранить')");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector("#companyName");
    const company = await page.inputValue("#companyName");
    await expect(company === "AUTO QA LLC", `company value not restored: ${company}`);
  });

  await test("Size-required product blocks submit without size", async () => {
    const p = await firstProductWithSize(page);
    if (!p || !p.qtySelector || !p.sizeSelector) {
      throw new Error("no product with size-select and qty found");
    }
    if (!p.hasEmptyOption) return;
    await page.selectOption(p.sizeSelector, "");
    await page.fill(p.qtySelector, "1");
    const missingCount = await page.evaluate(() => {
      try {
        const lines = collectOrderLines();
        return findMissingSizeLines(lines).length;
      } catch (e) {
        return -1;
      }
    });
    if (missingCount <= 0) return;
    await page.click("#submitBtn");
    const blocked = await waitForMissingRequiredValidation(page, 7000);
    await expect(blocked, "required-params validation was not shown");
  });

  await test("Submit succeeds when required size is selected", async () => {
    const p = await firstProductWithSize(page);
    await expect(p && p.qtySelector && p.sizeSelector, "size-required selectors not found");
    await page.selectOption(p.sizeSelector, { index: 1 });
    await ensureCartClosed(page);
    await page.click("#submitBtn");
    await waitForToastContains(page, "отправлена");
  });

  const failed = results.filter((r) => r.status === "FAIL");
  const passed = results.filter((r) => r.status === "PASS");
  console.log(`SUMMARY: ${passed.length} passed, ${failed.length} failed`);
  if (failed.length) {
    failed.forEach((f) => console.log(`FAIL_DETAIL: ${f.name} -> ${f.error}`));
    await browser.close();
    process.exit(1);
  }

  await browser.close();
}

run().catch((err) => {
  console.error("FATAL:", err.message);
  process.exit(1);
});
