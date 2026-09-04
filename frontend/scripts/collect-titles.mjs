// 收集全站渲染出的作品标题（ZH 模式 = 原始值）
import { chromium } from 'playwright-core';

const pages = [
  'https://molin.wiki/?lang=zh#/tiba',
  'https://molin.wiki/?lang=zh#/tiba/list',
  'https://molin.wiki/?lang=zh#/tiba/ranking',
  'https://molin.wiki/?lang=zh#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654',
];

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const all = new Set();
for (const url of pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'zh-CN' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(2500);
  try {
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 200)); }
    });
  } catch { /* ignore */ }
  await page.waitForTimeout(1000);
  const titles = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.gallery-title, .ranking-row-name, .work-title').forEach(e => {
      const t = e.textContent.trim(); if (t) out.push(t);
    });
    return out;
  });
  titles.forEach(t => all.add(t));
  await ctx.close();
}
await browser.close();
for (const t of [...all].sort()) console.log(t);
console.log('TOTAL:', all.size);
