// i18n 字典体检：重复键 / 中文残留 / 命名空间键缺漏。
// 用法: node scripts/i18n-check.mjs   （有重复键时退出码非 0，适合接 CI / pre-commit）
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/locales')
const CJK = /[\u4e00-\u9fff]/
// 只解析单行 "  'key': 'value'," 结构（本项目字典为纯扁平单行风格）
const LINE = /^ {2}'((?:[^'\\]|\\.)*)': '(.*)',\s*$/gm

function parse(file) {
  const src = fs.readFileSync(file, 'utf8')
  const rows = []
  for (const m of src.matchAll(LINE)) rows.push({ key: m[1], value: m[2], index: m.index })
  return rows
}

let errors = 0
const report = (file, msg) => { console.log(`${file}: ${msg}`); errors++ }

for (const name of ['zh.js', 'en.js']) {
  const file = path.join(dir, name)
  const rows = parse(file)
  const seen = new Map()
  for (const r of rows) {
    if (seen.has(r.key)) {
      report(name, `duplicate key '${r.key}' (line ${srcLine(file, r.index)}) — JS 后者胜出，前者被静默覆盖`)
    }
    seen.set(r.key, r)
  }
  // 英文值残留中文 = 漏译；HTML 实体经 {{ }} 文本插值会原样显示 = 禁用
  if (name === 'en.js') {
    for (const r of rows) {
      if (CJK.test(r.value)) report(name, `EN value still contains CJK for '${r.key}': ${r.value.slice(0, 40)}`)
    }
  }
  for (const r of rows) {
    if (/&#|&lt;|&gt;|&quot;/.test(r.value)) report(name, `HTML entity in value of '${r.key}' renders literally via text interpolation: ${r.value.slice(0, 40)}`)
  }
  // zh 缺 namespace 键（en 有而 zh 没有的 'a.b' 键会让中文界面显示原文 key）
  if (name === 'en.js') {
    const zhRows = new Set(parse(path.join(dir, 'zh.js')).map(r => r.key))
    for (const r of rows) {
      if (r.key.includes('.') && !zhRows.has(r.key)) {
        report('zh.js', `missing namespaced key '${r.key}' (present only in en)`)
      }
    }
  }
}

function srcLine(file, index) {
  const src = fs.readFileSync(file, 'utf8')
  return src.slice(0, index).split('\n').length
}

if (errors) {
  console.log(`\n✗ i18n-check: ${errors} problem(s)`)
  process.exit(1)
}
console.log('✓ i18n-check: 无重复键、无中文残留、命名空间键 zh/en 对齐')
