// 部署后验证：EN 模式下题跋页的标签芯片与 UI 字符串
import { chromium } from 'playwright-core';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
const page = await ctx.newPage();
try { await page.goto('https://molin.wiki/?lang=en#/tiba', { waitUntil: 'networkidle', timeout: 45000 }); } catch { await page.waitForTimeout(3000); }
await page.waitForTimeout(3000);

const res = await page.evaluate(() => {
  const tags = [...document.querySelectorAll('.info-tag')].map(e => e.textContent.trim()).slice(0, 30);
  const cardTitle = document.querySelector('.card-title')?.textContent.trim();
  const searchText = [...document.querySelectorAll('.gallery-card button')].map(e => e.textContent.trim()).filter(Boolean).slice(0, 5);
  const loadMore = document.querySelector('.gallery-load-more button')?.textContent.trim();
  const meta = [...document.querySelectorAll('.gallery-meta .meta-col')].map(e => e.textContent.trim()).slice(0, 8);
  return { cardTitle, searchText, loadMore, tags, meta, htmlLang: document.documentElement.lang };
});
console.log(JSON.stringify(res, null, 2));
await browser.close();
