// EN vs ZH 排版测量：关键文本节点的字体/字号/行高/颜色对比
import { chromium } from 'playwright-core';

const SAMPLES = [
  ['card-title', '.card-title'],
  ['h3-stats', 'h3.stats-title'],
  ['gallery-title', '.gallery-title'],
  ['info-tag', '.info-tag'],
  ['nav-title', '.nav-title'],
  ['summary-reasoning', '.summary-reasoning'],
  ['tbc-label', '.tbc-label'],
  ['meta', '.gallery-meta .meta-col'],
  ['bar-label', '.bar-label-center'],
  ['ranking-name', '.ranking-row-name'],
  ['nav-text', '.nav-text'],
];

async function measure(ctx, url, selector) {
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(2500); }
  await page.waitForTimeout(2000);
  const res = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { font: cs.fontFamily.slice(0, 40), size: cs.fontSize, weight: cs.fontWeight, lh: cs.lineHeight, color: cs.color, ls: cs.letterSpacing, text: el.textContent.trim().slice(0, 30) };
  }, selector);
  await page.close();
  return res;
}

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctxEn = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
const ctxZh = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'zh-CN' });

const urlEn = 'https://molin.wiki/?lang=en#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654';
const urlZh = 'https://molin.wiki/?lang=zh#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654';

for (const [name, sel] of SAMPLES) {
  const en = await measure(ctxEn, urlEn, sel);
  const zh = await measure(ctxZh, urlZh, sel);
  if (!en) { console.log(name, ': no el'); continue; }
  console.log(`${name} (${sel})`);
  console.log(`  EN size=${en.size} lh=${en.lh} w=${en.weight} ls=${en.ls} color=${en.color} font=${en.font}  | ${en.text}`);
  console.log(`  ZH size=${zh.size} lh=${zh.lh} w=${zh.weight} ls=${zh.ls} color=${zh.color} font=${zh.font}  | ${zh.text}`);
}
await browser.close();
