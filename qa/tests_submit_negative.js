const { chromium } = require("playwright");

const SITE_URL = "https://timur-ship-it.github.io/logist-city/";
const GOOGLE_SCRIPT_RE = /script\.google\.com\/macros\/s\/.*\/exec/;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const requests = [];
  page.on("request", (req) => {
    if (GOOGLE_SCRIPT_RE.test(req.url()) && req.method() === "POST") {
      requests.push({ at: Date.now(), url: req.url() });
    }
  });

  const out = [];

  // Scenario 1: required company field missing
  await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("#submitBtn", { timeout: 20000 });
  await page.fill("#contactPerson", "Neg Tester");
  await page.fill("#contactEmail", "neg1@example.com");
  requests.length = 0;
  await page.click("#submitBtn");
  await sleep(900);
  const toast1 = await page.locator("#toast").innerText().catch(() => "");
  out.push({
    scenario: "missing_company",
    toast: toast1,
    blocked: /название компании/i.test(toast1),
    postRequests: requests.length,
  });

  // Scenario 2: required selector missing for size-required product
  await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("#submitBtn", { timeout: 20000 });
  await page.fill("#companyName", "NEG-REQ-FIELD");
  await page.fill("#contactPerson", "Neg Tester");
  await page.fill("#contactEmail", "neg2@example.com");
  await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll(".product"))
      .filter((c) => c.dataset.removed !== "true" && c.style.display !== "none");
    for (const card of cards) {
      const id = card.dataset.id;
      const qty = card.querySelector(`.qty-input[data-qty="${id}"]`);
      const sel = card.querySelector(`select[data-size="${id}"]`);
      if (!qty || !sel) continue;
      const hasEmpty = Array.from(sel.options || []).some((o) => o.value === "");
      if (!hasEmpty) continue;
      sel.value = "";
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      qty.value = "1";
      qty.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }
    return false;
  });
  requests.length = 0;
  await page.click("#submitBtn");
  await sleep(1400);
  const toast2 = await page.locator("#toast").innerText().catch(() => "");
  const cartOpen = await page.evaluate(() => {
    const drawer = document.getElementById("cartDrawer");
    return !!drawer && drawer.classList.contains("open");
  });
  const warningCount = await page.locator(".cart-warning").count();
  out.push({
    scenario: "missing_required_select",
    toast: toast2,
    blocked:
      /обязательные параметры|типоразмер/i.test(toast2) || warningCount > 0,
    cartOpen,
    cartWarningPresent: warningCount > 0,
    postRequests: requests.length,
  });

  console.log(JSON.stringify(out, null, 2));
  await browser.close();

  const failed = out.filter((r) => !r.blocked || r.postRequests > 0);
  process.exit(failed.length ? 1 : 0);
}

run().catch((err) => {
  console.error("FATAL:", err.message);
  process.exit(1);
});

