// 收集各题跋页面实际渲染出的标签芯片文本（ZH 模式 = 原始值），输出唯一集合
import { chromium } from 'playwright-core';

const pages = [
  'https://molin.wiki/#/tiba?lang=zh',
  'https://molin.wiki/#/tiba/list?lang=zh',
  'https://molin.wiki/#/tiba/ranking?lang=zh',
  'https://molin.wiki/#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654?lang=zh',
];

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const all = new Set();
for (const url of pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'zh-CN' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(2500);
  // 滚到底触发懒加载
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 800) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 200)); }
  });
  await page.waitForTimeout(1500);
  const tags = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.info-tag').forEach(el => { const t = el.textContent.trim(); if (t) out.push(t); });
    return out;
  });
  tags.forEach(t => all.add(t));
  console.log(url.split('#')[1].split('?')[0], '->', tags.length, 'chips');
  await ctx.close();
}
await browser.close();
console.log('=== UNIQUE TAGS ===');
for (const t of [...all].sort()) console.log(t);
