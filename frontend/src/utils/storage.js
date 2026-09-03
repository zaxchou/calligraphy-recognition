/**
 * v2.0 §3.6 — 统一 localStorage 访问层。
 *
 * 解决的问题：19 个文件手工读写 localStorage，无版本号、无 schema 容错、
 * JSON.parse 崩溃会白屏。统一走本模块：
 *  - 所有读写 try/catch 兜底（隐私模式/配额溢出不再抛错）
 *  - 数据带版本号，字段变更时旧数据自动丢弃
 *  - get 返回解析后的对象或 fallback，绝不抛异常
 */

const VERSION = 1

function _wrap(value) {
  return JSON.stringify({ v: VERSION, data: value })
}

function _unwrap(raw) {
  const parsed = JSON.parse(raw)
  // 旧格式（无版本号包裹）直接返回原始值，兼容存量
  if (parsed && typeof parsed === 'object' && 'v' in parsed && 'data' in parsed) {
    return parsed.v === VERSION ? parsed.data : null
  }
  return parsed
}

/** 安全读取对象；损坏/缺失返回 fallback */
export function getStorageJson(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    if (raw == null) return fallback
    const parsed = _unwrap(raw)
    return parsed === null ? fallback : parsed
  } catch {
    return fallback
  }
}

/** 安全写入对象；配额溢出静默失败并返回 false */
export function setStorageJson(key, value) {
  try {
    localStorage.setItem(key, _wrap(value))
    return true
  } catch {
    return false
  }
}

/** 安全读取字符串 */
export function getStorageString(key, fallback = '') {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

/** 安全写入字符串 */
export function setStorageString(key, value) {
  try {
    localStorage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

/** 安全删除 */
export function removeStorage(key) {
  try {
    localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}
