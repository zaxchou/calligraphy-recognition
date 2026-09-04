// EN 溢出精查：定位 tiba-list 与 tiba-detail 中溢出父容器元素的文本与几何信息
import { chromium } from 'playwright-core';

const pages = [
  { name: 'tiba-list', url: 'https://molin.wiki/#/tiba?lang=en' },
  { name: 'tiba-detail', url: 'https://molin.wiki/#/tiba/ba88ab6a-4f31-4a72-a26a-2b9b6d098654?lang=en' },
];

const browser = await chromium.launch({ channel: 'msedge', headless: true });
for (const p of pages) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'en-US' });
  const page = await ctx.newPage();
  try {
    await page.goto(p.url, { waitUntil: 'networkidle', timeout: 45000 });
  } catch { await page.waitForTimeout(3000); }
  await page.waitForTimeout(2500);

  const found = await page.evaluate(() => {
    const out = [];
    const all = document.querySelectorAll('*');
    for (const el of all) {
      if (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2) {
        const cs = getComputedStyle(el);
        if (cs.overflowX === 'auto' || cs.overflowX === 'scroll' || cs.overflowY === 'auto' || cs.overflowY === 'scroll') continue;
        // 只关心叶子附近有文本的元素
        const text = (el.innerText || '').trim().slice(0, 80).replace(/\n/g, ' | ');
        if (!text) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        out.push({
          tag: el.tagName.toLowerCase(),
          cls: String(el.className).slice(0, 60),
          w: Math.round(r.width), h: Math.round(r.height),
          sw: el.scrollWidth, sh: el.scrollHeight,
          cw: el.clientWidth, ch: el.clientHeight,
          text,
        });
      }
    }
    return out.slice(0, 12);
  });

  console.log('===', p.name, '===');
  for (const f of found) {
    console.log(`<${f.tag} class="${f.cls}"> box=${f.w}x${f.h} scroll=${f.sw}x${f.sh} client=${f.cw}x${f.ch}`);
    console.log('   text:', f.text);
  }
  if (!found.length) console.log('OK - no clipped text containers');
  await ctx.close();
}
await browser.close();
