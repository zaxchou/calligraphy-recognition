// EN 全站泄漏扫描：公开页面在 EN 模式下残留的可见中文文本
import { chromium } from 'playwright-core';

const CJK = /[\u4e00-\u9fff]/;
const pages = [
  ['home', 'https://molin.wiki/?lang=en#/'],
  ['artists', 'https://molin.wiki/?lang=en#/artists'],
  ['tiba-home', 'https://molin.wiki/?lang=en#/tiba'],
  ['tiba-list', 'https://molin.wiki/?lang=en#/tiba/list'],
  ['tiba-detail', 'https://molin.wiki/?lang=en#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654'],
  ['knowledge', 'https://molin.wiki/?lang=en#/knowledge'],
];

const browser = await chromium.launch({ channel: 'msedge', headless: true });
for (const [name, url] of pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(2500);
  try {
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 900) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
      window.scrollTo(0, 0);
    });
  } catch { /* hash 路由可能触发导航，忽略 */ }
  await page.waitForTimeout(800);

  let leaks = [];
  try { leaks = await page.evaluate(() => {
    const out = new Map();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent.trim();
      if (!text || !/[\u4e00-\u9fff]/.test(text)) continue;
      const el = node.parentElement;
      if (!el) continue;
      // 跳过脚本/样式和不可见元素
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      // 找最近的带 class 祖先，便于定位来源
      let src = el;
      for (let i = 0; i < 4 && src.parentElement; i++) { if (src.className && typeof src.className === 'string' && src.className.trim()) break; src = src.parentElement; }
      const key = text.slice(0, 60);
      if (!out.has(key)) out.set(key, `${el.tagName.toLowerCase()}@${(typeof src.className === 'string' ? src.className : '').split(' ')[0] || '(anon)'}`);
    }
    return [...out.entries()].slice(0, 40);
  });
  } catch { /* ignore nav destroy */ }

  console.log(`=== ${name}: ${leaks.length} 条残留中文 ===`);
  for (const [text, loc] of leaks) console.log(`  [${loc}] ${text}`);
  await ctx.close();
}
await browser.close();
