const { chromium } = require("playwright");

const SITE_URL = "https://timur-ship-it.github.io/logist-city/";
const SLOW_MO = Number(process.env.SLOW_MO || 900);
const STEP_PAUSE_MS = Number(process.env.STEP_PAUSE_MS || 1800);
const HOLD_MS = Number(process.env.HOLD_MS || 180000);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function clickWithLog(page, selector, note) {
  console.log(`STEP: ${note}`);
  await page.click(selector);
  await sleep(STEP_PAUSE_MS);
}

async function fillWithLog(page, selector, value, note) {
  console.log(`STEP: ${note}`);
  await page.fill(selector, value);
  await sleep(STEP_PAUSE_MS);
}

async function pickProducts(page) {
  return page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll(".product"))
      .filter((c) => c.dataset.removed !== "true" && c.style.display !== "none");
    const picked = [];

    const chooseRequired = (card) => {
      const selects = Array.from(card.querySelectorAll(".prod-inputs .size-wrap > select.size-select"));
      for (const sel of selects) {
        const label = (
          sel.closest(".size-wrap")?.querySelector("label")?.textContent || ""
        ).trim().toLowerCase();
        if (label.includes("цвет")) continue;
        const opt = Array.from(sel.options || []).find(
          (o) => o.value && !/свой размер/i.test(String(o.value))
        );
        if (!opt) return false;
        sel.value = String(opt.value);
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return true;
    };

    for (const card of cards) {
      if (picked.length >= 3) break;
      const id = card.dataset.id;
      const qty = card.querySelector(`.qty-input[data-qty="${id}"]`) || card.querySelector(".qty-input");
      if (!qty) continue;
      if (!chooseRequired(card)) continue;
      qty.value = "1";
      qty.dispatchEvent(new Event("input", { bubbles: true }));
      picked.push({
        id,
        title: (card.querySelector(".prod-name")?.textContent || "").trim(),
      });
    }

    return picked;
  });
}

async function run() {
  const browser = await chromium.launch({ headless: false, slowMo: SLOW_MO });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log("STEP: open site");
  await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("#submitBtn", { timeout: 20000 });
  await sleep(STEP_PAUSE_MS);

  await fillWithLog(page, "#companyName", `LIVE-WATCH-${Date.now()}`, "fill company");
  await fillWithLog(page, "#contactPerson", "Playwright Live", "fill contact person");
  await fillWithLog(page, "#contactEmail", `live-${Date.now()}@example.com`, "fill email");
  await fillWithLog(page, "#projectName", "Live watch run", "fill project");

  console.log("STEP: pick products and set qty/selectors");
  const picked = await pickProducts(page);
  console.log("PICKED:", picked);
  await sleep(STEP_PAUSE_MS);

  await clickWithLog(page, "#cartFabBtn", "open cart");
  await sleep(STEP_PAUSE_MS);
  await clickWithLog(page, ".cart-close", "close cart");
  await sleep(STEP_PAUSE_MS);

  await clickWithLog(page, "#submitBtn", "submit order");
  await sleep(Math.max(2500, STEP_PAUSE_MS));

  const toast = await page.locator("#toast").innerText().catch(() => "");
  console.log("TOAST:", toast);
  console.log(`INFO: browser stays open for observation (${Math.round(HOLD_MS / 1000)} sec).`);
  await sleep(HOLD_MS);
}

run().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
