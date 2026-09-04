// 终检：排行页/艺术家页 EN 泄漏 + 下拉选中项 + 标题英文化
import { chromium } from 'playwright-core';
const CJK = /[\u4e00-\u9fff]/;
const pages = [
  ['tiba-ranking', 'https://molin.wiki/?lang=en#/tiba/ranking'],
  ['tiba-detail', 'https://molin.wiki/?lang=en#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654'],
  ['artist-works', 'https://molin.wiki/?lang=en#/artist/%E6%9D%8E%E9%B1%93/works'],
];
const browser = await chromium.launch({ channel: 'msedge', headless: true });
for (const [name, url] of pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(3000);
  const res = await page.evaluate(() => {
    const out = {};
    // 剩余中文（排除语言按钮/ICP）
    const leaks = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const n = walker.currentNode;
      const txt = n.textContent.trim();
      if (!txt || !/[\u4e00-\u9fff]/.test(txt)) continue;
      const el = n.parentElement;
      let src = el;
      for (let i = 0; i < 4 && src.parentElement; i++) { if (src.className && typeof src.className === 'string' && src.className.trim()) break; src = src.parentElement; }
      const loc = `${el.tagName.toLowerCase()}@${(typeof src.className === 'string' ? src.className : '').split(' ')[0] || '(anon)'}`;
      if (/lang-switch|fa-row|备案/.test(loc)) continue;
      leaks.push(`[${loc}] ${txt.slice(0, 40)}`);
    }
    out.leaks = [...new Set(leaks)].slice(0, 20);
    // 下拉选中显示
    out.selects = [...document.querySelectorAll('.el-select__selected-item')].map(e => e.textContent.trim()).slice(0, 6);
    // 抽样标题
    out.sampleTitles = [...document.querySelectorAll('.work-title, .aw-title, .ranking-row-name')].slice(0, 6).map(e => e.textContent.trim());
    return out;
  });
  console.log(`=== ${name}`);
  console.log('selects:', JSON.stringify(res.selects));
  console.log('titles:', JSON.stringify(res.sampleTitles));
  console.log(res.leaks.length ? 'leaks:\n  ' + res.leaks.join('\n  ') : 'leaks: none');
  await ctx.close();
}
await browser.close();
