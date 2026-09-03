// i18n 批量扫描：统计 src 下所有残留中文，输出 JSON 报告供批量词条生成用。
// 用法: node scripts/i18n-scan.mjs [--json out.json]
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src')
const CJK = /[\u{4e00}-\u{9fff}\u{3000}-\u{303f}\u{ff00}-\u{ffef}]/u
const outJson = process.argv.includes('--json') ? process.argv[process.argv.indexOf('--json') + 1] : null

function walk(dir, files = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, files)
    else if (/\.(vue|js|ts)$/.test(e.name)) files.push(p)
  }
  return files
}

// 去注释（粗粒度：模板注释、行注释、块注释；字符串内的 // 不处理，够用）
function stripComments(code, isVue) {
  return code
    .replace(/<!--[\s\S]*?-->/g, m => ' '.repeat(m.length))
    .replace(/\/\*[\s\S]*?\*\//g, m => ' '.repeat(m.length))
    .replace(/(^|[^:"'`\\])\/\/[^\n]*/g, (m, p1) => p1 + ' '.repeat(m.length - p1.length))
}

function scanFile(file) {
  const rel = path.relative(root, file).replace(/\\/g, '/')
  const code = stripComments(fs.readFileSync(file, 'utf8'), rel.endsWith('.vue'))
  const hits = []

  const add = (line, col, text, kind, raw) => {
    if (CJK.test(text)) hits.push({ line, col, kind, text: text.trim(), raw })
  }

  if (rel.endsWith('.vue')) {
    const template = code.match(/<template[\s\S]*<\/template>/)?.[0] ?? ''
    // 1) 模板文本节点：>中文<
    for (const m of template.matchAll(/>([^<>]*)</g)) {
      const t = m[1]
      if (CJK.test(t)) {
        const line = code.slice(0, m.index).split('\n').length
        add(line, 0, t, 'text', t.trim())
      }
    }
    // 2) 静态属性：placeholder="中文"
    for (const m of template.matchAll(/([\w-]+)="([^"]*[\u{4e00}-\u{9fff}][^"]*)"/gu)) {
      const line = code.slice(0, m.index).split('\n').length
      add(line, 0, m[2], `attr:${m[1]}`, m[0])
    }
    // 3) 绑定中的字面量：:label="'中文'"
    for (const m of template.matchAll(/:[\w-]+="'([^']*[\u{4e00}-\u{9fff}][^']*)'"/gu)) {
      const line = code.slice(0, m.index).split('\n').length
      add(line, 0, m[1], 'bind', m[0])
    }
    // 4) script 段字符串字面量
    const script = code.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? ''
    scanScript(script, code.indexOf(script), add)
  } else {
    scanScript(code, 0, add)
  }
  return { file: rel, hits }
}

function scanScript(code, offset, add) {
  for (const m of code.matchAll(/'([^'\\\n]*)'|"([^"\\\n]*)"|`([^`\\]*)`/g)) {
    const s = m[1] ?? m[2] ?? m[3] ?? ''
    if (!CJK.test(s)) continue
    const line = code.slice(0, m.index).split('\n').length
    add(line, 0, s, 'script', s)
  }
}

const files = walk(root)
const results = files.map(scanFile).filter(r => r.hits.length)
const byFile = {}
const kindCount = {}
const uniq = new Map()
for (const r of results) {
  byFile[r.file] = r.hits.length
  for (const h of r.hits) {
    kindCount[h.kind] = (kindCount[h.kind] ?? 0) + 1
    const key = h.kind === 'script' ? `S::${h.text}` : `${h.kind.split(':')[0]}::${h.text}`
    if (!uniq.has(key)) uniq.set(key, { text: h.text, kind: h.kind.split(':')[0], files: [] })
    uniq.get(key).files.push(`${r.file}:${h.line}`)
  }
}

const summary = {
  filesWithChinese: results.length,
  totalHits: Object.values(byFile).reduce((a, b) => a + b, 0),
  uniqueStrings: uniq.size,
  byKind: kindCount,
  top30: Object.entries(byFile).sort((a, b) => b[1] - a[1]).slice(0, 30),
}
console.log(JSON.stringify(summary, null, 2))
if (outJson) {
  fs.writeFileSync(outJson, JSON.stringify({ summary, strings: [...uniq.values()] }, null, 2), 'utf8')
  console.log(`\nfull report -> ${outJson}`)
}
