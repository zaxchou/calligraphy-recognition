// 把人工翻译 (scripts/i18n-en-patch.json: {key: en}) 合入 en.js，新词条合入 zh.js。
// 用法: node scripts/i18n-merge-en.mjs
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const localesDir = path.resolve(scriptDir, '../src/locales')
const PENDING = path.join(scriptDir, 'i18n-pending.json')
const PATCH = path.join(scriptDir, 'i18n-en-patch.json')

const pending = JSON.parse(fs.readFileSync(PENDING, 'utf8'))
const patch = JSON.parse(fs.readFileSync(PATCH, 'utf8'))

const q = s => String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n')

function appendEntries(file, pairs) {
  if (!pairs.length) return 0
  let txt = fs.readFileSync(file, 'utf8')
  const block = pairs.map(([k, v]) => `  '${q(k)}': '${q(v)}',`).join('\n')
  const i = txt.lastIndexOf('}')
  txt = txt.slice(0, i) + `  // === codemod batch ===\n` + block + '\n' + txt.slice(i)
  fs.writeFileSync(file, txt, 'utf8')
  return pairs.length
}

const en = [], zh = [], skipped = []
for (const [key, translation] of Object.entries(patch)) {
  if (!(key in pending)) { skipped.push(key); continue }
  if (/[\u{4e00}-\u{9fff}]/u.test(translation)) { console.error(`!! ${key} 英文含中文: ${translation}`); continue }
  en.push([key, translation])
  zh.push([key, pending[key]])
  delete pending[key]
}

const nEn = appendEntries(path.join(localesDir, 'en.js'), en)
const nZh = appendEntries(path.join(localesDir, 'zh.js'), zh)
fs.writeFileSync(PENDING, JSON.stringify(pending, null, 2), 'utf8')

console.log(`合入 en.js: ${nEn} 条, zh.js: ${nZh} 条, 跳过 ${skipped.length}, 剩余待翻译 ${Object.keys(pending).length}`)
if (nEn) console.log('→ 记得把 en-patch.json 清空或更新为下一批内容')
