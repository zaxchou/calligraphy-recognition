// 收集艺术家页(works)、排行页、作品库页渲染出的作品标题（ZH）
import { chromium } from 'playwright-core';

const urls = [
  'https://molin.wiki/?lang=zh#/tiba/ranking',
  'https://molin.wiki/?lang=zh#/artist/%E6%9D%8E%E9%B1%93/works',
  'https://molin.wiki/?lang=zh#/artist/%E9%83%91%E7%87%AE/works',
  'https://molin.wiki/?lang=zh#/artist/%E5%BE%90%E6%B8%AD/works',
  'https://molin.wiki/?lang=zh#/artist/%E9%99%88%E6%B7%B3/works',
  'https://molin.wiki/?lang=zh#/artist/%E6%9C%B1%E8%80%BB/works',
  'https://molin.wiki/?lang=zh#/artist/%E6%BD%98%E5%A4%A9%E5%AF%BF/works',
  'https://molin.wiki/?lang=zh#/artist/%E5%88%98%E6%B5%B7%E5%8B%87/works',
];

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const all = new Set();
for (const url of urls) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'zh-CN' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(2500);
  try {
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
    });
  } catch { /* ignore */ }
  await page.waitForTimeout(800);
  const titles = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.aw-title, .aw-table-title, .work-title, .gallery-title, .ranking-row-name, .nav-title, .artwork-title').forEach(e => {
      const s = e.textContent.trim();
      if (s && !/^\s*$/.test(s)) out.push(s);
    });
    return out;
  });
  titles.forEach(x => all.add(x));
  console.log(url.split('#')[1].split('?')[0], '->', titles.length);
  await ctx.close();
}
await browser.close();
console.log('=== UNIQUE ===');
for (const t of [...all].sort()) console.log(t);
console.log('TOTAL:', all.size);
