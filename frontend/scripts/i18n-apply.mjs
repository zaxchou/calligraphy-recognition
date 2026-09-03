// i18n 批量改造（codemod）：把残留中文替换为 $t()/t() 调用，只做高置信度替换。
// 用法: node scripts/i18n-apply.mjs <file1> <file2> ...
// 产物:
//   scripts/i18n-dict.json    中文 -> key 映射（跨批次累积，已有 zh.js 词条优先复用）
//   scripts/i18n-pending.json 累计新增词条 {key: 中文}，人工翻译后经 i18n-merge-en.mjs 合入
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(scriptDir, '../src')
const DICT_FILE = path.join(scriptDir, 'i18n-dict.json')
const PENDING_FILE = path.join(scriptDir, 'i18n-pending.json')

const targets = process.argv.slice(2).map(p => path.resolve(p))
if (!targets.length) { console.error('用法: node scripts/i18n-apply.mjs <files...>'); process.exit(1) }

// ── 载入既有词条：zh.js 的 value -> key 复用 ──
function parseFlatDict(file) {
  const map = {}
  for (const m of fs.readFileSync(file, 'utf8').matchAll(/'((?:[^'\\]|\\.)+)'\s*:\s*'((?:[^'\\]|\\.)*)'/g)) {
    if (!(m[2] in map)) map[m[2]] = m[1]
  }
  return map
}
const zhValueToKey = parseFlatDict(path.join(srcRoot, 'locales/zh.js'))

const dict = fs.existsSync(DICT_FILE) ? JSON.parse(fs.readFileSync(DICT_FILE, 'utf8')) : {}
const newEntries = {}   // key -> zh（本批新增）

// 高频公共词先归到 common.*
const COMMON = {
  '确定': 'common.confirm', '取消': 'common.cancel', '保存': 'common.save', '删除': 'common.delete',
  '编辑': 'common.edit', '搜索': 'common.search', '加载中...': 'common.loading', '加载中…': 'common.loading',
  '登录': 'common.login', '注册': 'common.register', '退出登录': 'common.logout', '提交': 'common.submit',
  '操作成功': 'common.success', '操作失败': 'common.failure', '成功': 'common.ok', '失败': 'common.failed',
  '全部': 'common.all', '更多': 'common.more', '关闭': 'common.close',
  '提示': 'common.tip', '警告': 'common.warning', '错误': 'common.error',
  '上传': 'common.upload', '下载': 'common.download', '刷新': 'common.refresh', '重置': 'common.reset',
  '详情': 'common.detail', '返回': 'common.back', '首页': 'nav.home', '设置': 'common.settings',
}
for (const [zh, key] of Object.entries(COMMON)) dict[zh] ??= key

function nsFor(file) {
  const rel = path.relative(srcRoot, file).replace(/\\/g, '/').replace(/\.(vue|js|ts)$/, '')
  return rel.replace(/^views\//, '').replace(/^components\//, 'c-').replace(/\//g, '.').toLowerCase()
}
const counter = {}
function keyFor(zh, ns, kind) {
  if (dict[zh]) return dict[zh]
  if (zhValueToKey[zh]) { dict[zh] = zhValueToKey[zh]; return dict[zh] }
  counter[ns] ??= { t: 0, a: 0, s: 0 }
  const k = `${ns}.${kind}${++counter[ns][kind]}`
  dict[zh] = k
  newEntries[k] = zh
  return k
}

// 比较/条件表达式中出现的字面量 → 跳过（避免改坏逻辑）
function comparisonLiterals(code) {
  const bad = new Set()
  for (const m of code.matchAll(/(?:===|!==|==|!=)\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g)) bad.add(m[1].slice(1, -1))
  for (const m of code.matchAll(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*(?:===|!==|==|!=)/g)) bad.add(m[1].slice(1, -1))
  return bad
}

// 静态属性白名单；(?<![\w:>@-]) 防止命中 :label= 的内层、prev-text 里的 text
const ATTR_RE = new RegExp('(?<![\\w:>@-])(label|placeholder|title|description|content|alt|aria-label|empty-text|prev-text|next-text|tooltip|tip|header)="([^"\'{}]*[\\u{4e00}-\\u{9fff}][^"\'{}]*)"', 'gu')
const OBJ_RE = new RegExp("(label|title|placeholder|message|tip)\\s*:\\s*'((?:[^'\\\\]|\\\\.)*[\\u{4e00}-\\u{9fff}](?:[^'\\\\]|\\\\.)*)'", 'gu')

function injectImport(script) {
  if (/useI18n\s*\(/.test(script)) return script   // 已有 t（const { t } = useI18n()）
  const line = "import { translate as t } from '@/locales'"
  const imports = [...script.matchAll(/^import .*$/gm)]
  if (imports.length) {
    const last = imports[imports.length - 1]
    const idx = script.indexOf(last[0]) + last[0].length
    return script.slice(0, idx) + '\n' + line + script.slice(idx)
  }
  return line + '\n' + script
}

let totalReplaced = 0, totalSkipped = 0

for (const file of targets) {
  const ns = nsFor(file)
  const code = fs.readFileSync(file, 'utf8')
  let replaced = 0, skipped = 0

  // ── script 改造 ──
  const transformScript = (script) => {
    const bad = comparisonLiterals(script)
    let s = script
    const SUBS = [
      /(ElMessage(?:\.(?:success|error|warning|info))?\()(\s*)'((?:[^'\\]|\\.)*)'(\s*\))/g,
      /(ElMessageBox\.(?:confirm|alert)\()(\s*)'((?:[^'\\]|\\.)*)'(\s*,)/g,
      /(ElNotification(?:\.(?:success|error|warning|info))?\()(\s*)'((?:[^'\\]|\\.)*)'(\s*\))/g,
      /((?:^|[^.\w])confirm\()(\s*)'((?:[^'\\]|\\.)*)'(\s*\))/gm,
      /((?:^|[^.\w])alert\()(\s*)'((?:[^'\\]|\\.)*)'(\s*\))/gm,
    ]
    for (const re of SUBS) {
      s = s.replace(re, (m, pre, sp, inner, post) => {
        if (bad.has(inner) || inner.includes('${')) { skipped++; return m }
        replaced++
        return `${pre}${sp}t('${keyFor(inner, ns, 's')}')${post}`
      })
    }
    s = s.replace(OBJ_RE, (m, kw, val) => {
      if (bad.has(val) || val.includes('${')) { skipped++; return m }
      replaced++
      return `${kw}: t('${keyFor(val, ns, 's')}')`
    })
    return s
  }

  let newCode = code
  const scRe = /(<script[^>]*>)([\s\S]*?)(<\/script>)/
  const sc = newCode.match(scRe)
  if (sc) {
    const inner = transformScript(sc[2])
    const injected = inner !== sc[2] ? injectImport(inner) : inner
    const i = newCode.indexOf(sc[0])
    newCode = newCode.slice(0, i) + sc[1] + injected + sc[3] + newCode.slice(i + sc[0].length)
  } else {
    newCode = transformScript(newCode)
    if (newCode !== code) newCode = injectImport(newCode)
  }

  // ── 模板改造（script 段之外） ──
  const tplMatch = newCode.match(/<template[\s\S]*<\/template>/)
  if (tplMatch) {
    let tpl = tplMatch[0]
    // 1) 纯文本节点（单行、不含 mustache；字母+数字混合视为动态，跳过）
    tpl = tpl.replace(/>(\s*)([^<>{}\n]*[\u{4e00}-\u{9fff}][^<>{}\n]*)(\s*)</gu, (m, pre, text, post) => {
      if (/[\d]/.test(text) && /[a-zA-Z]/.test(text)) { skipped++; return m }
      const key = keyFor(text.trim(), ns, 't')
      replaced++
      return `>${pre}{{ $t('${key}') }}${post}<`
    })
    // 2) 白名单静态属性
    tpl = tpl.replace(ATTR_RE, (m, attr, val) => {
      const key = keyFor(val.trim(), ns, 'a')
      replaced++
      return `:${attr}="$t('${key}')"`
    })
    newCode = newCode.slice(0, tplMatch.index) + tpl + newCode.slice(tplMatch.index + tplMatch[0].length)
  }

  if (newCode !== code) {
    fs.writeFileSync(file, newCode, 'utf8')
    console.log(`${path.relative(srcRoot, file)}: 替换 ${replaced}, 跳过 ${skipped}`)
  } else {
    console.log(`${path.relative(srcRoot, file)}: 无改动 (跳过 ${skipped})`)
  }
  totalReplaced += replaced; totalSkipped += skipped
}

fs.writeFileSync(DICT_FILE, JSON.stringify(dict, null, 2), 'utf8')
const oldPending = fs.existsSync(PENDING_FILE) ? JSON.parse(fs.readFileSync(PENDING_FILE, 'utf8')) : {}
Object.assign(oldPending, newEntries)
fs.writeFileSync(PENDING_FILE, JSON.stringify(oldPending, null, 2), 'utf8')
console.log(`\n合计: 替换 ${totalReplaced}, 跳过 ${totalSkipped}, 新词条 ${Object.keys(newEntries).length} (累计待翻译 ${Object.keys(oldPending).length})`)
