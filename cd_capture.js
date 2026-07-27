// Frame grabber: drives window.setT(t) and screenshots each frame.
// Usage: node dd_capture.js <html> <framesDir> <fps> <seconds> <scale> <startIndex>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const [,, inPath, dir, fpsArg, secArg, scaleArg, startArg] = process.argv;
  const fps = parseInt(fpsArg, 10);
  const seconds = parseFloat(secArg);
  const scale = scaleArg ? parseFloat(scaleArg) : 1;
  const start = startArg ? parseInt(startArg, 10) : 0;
  const W = 1080, H = 1920;
  fs.mkdirSync(dir, { recursive: true });
  // channel:'chromium' uses the full Chromium build (installed by `playwright
  // install chromium`) rather than the separate headless_shell download — one
  // fewer binary to fetch, and it renders identically. Works on mac + Linux CI.
  const browser = await chromium.launch({ channel: 'chromium', args: ['--force-color-profile=srgb'] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  await page.goto('file://' + path.resolve(inPath), { waitUntil: 'networkidle' });
  await page.evaluate(async () => { if (document.fonts && document.fonts.ready) await document.fonts.ready; });
  await page.waitForTimeout(300);
  const total = Math.round(fps * seconds);
  for (let i = 0; i < total; i++) {
    await page.evaluate((tt) => window.setT(tt), i / fps);
    await page.screenshot({ path: path.join(dir, 'f' + String(start + i).padStart(5, '0') + '.png'),
                            clip: { x: 0, y: 0, width: W, height: H } });
  }
  await browser.close();
  console.log('captured', total, 'frames ->', dir);
})();
