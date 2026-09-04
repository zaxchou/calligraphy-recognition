import { chromium } from 'playwright-core';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
const page = await ctx.newPage();
try { await page.goto('https://molin.wiki/?lang=en#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654', { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
await page.waitForTimeout(3000);
// 点开 stats-header 内的 select
const opened = await page.evaluate(() => {
  const sel = document.querySelector('.stats-header .el-select__wrapper, .stats-header .el-select');
  if (!sel) return 'no stats select';
  const wrapper = document.querySelector('.stats-header .el-select__wrapper');
  if (wrapper) { wrapper.click(); return 'clicked wrapper'; }
  return 'no wrapper';
});
console.log('open:', opened);
await page.waitForTimeout(800);
const items = await page.evaluate(() => {
  const dd = [...document.querySelectorAll('.el-select-dropdown:not([style*="display: none"])')];
  return dd.map(d => ({ hidden: d.style.display, items: [...d.querySelectorAll('.el-select-dropdown__item')].map(e => e.textContent.trim()).slice(0, 15) })).filter(x => x.items.length);
});
console.log(JSON.stringify(items.slice(0, 3), null, 1));
await browser.close();
