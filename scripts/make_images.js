// Render scripts/og.html to the share card and icons in src/public/ (not part of build.sh; rerun after a design change).
//   NODE_PATH=$(npm root -g) node scripts/make_images.js     needs Playwright with Chromium, and network for the fonts
// Then make favicon.ico from favicon-48.png and delete the PNG: python3 -c "from PIL import Image; Image.open('src/public/favicon-48.png').save('src/public/favicon.ico')"
const { chromium } = require("playwright");
const path = require("path");
const root = path.dirname(__dirname);
const out = f => path.join(root, "src", "public", f);
const url = "file://" + path.join(root, "scripts", "og.html");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 1200 } });
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  await page.locator("#og").screenshot({ path: out("og.png") });
  for (const [name, size] of [["apple-touch-icon.png", 180], ["icon-192.png", 192], ["icon-512.png", 512], ["favicon-48.png", 48]]) {
    const p = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: size / 512 });
    await p.goto(url);
    await p.locator("#icon").screenshot({ path: out(name) });
    await p.close();
  }
  await browser.close();
})();
