/**
 * 字符级 diff 工具 — 用于变更审核的新旧值对比高亮
 *
 * 输入两个字符串，输出一个操作序列：
 *   { type: 'same' | 'added' | 'removed', text: string }
 *
 * 基于最长公共子序列(LCS)算法，按字符粒度对比。
 */

function lcs(a, b) {
  const m = a.length, n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  return dp
}

function backtrack(dp, a, b, i, j) {
  const result = []
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.push({ type: 'same', text: a[i - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'added', text: b[j - 1] })
      j--
    } else {
      result.push({ type: 'removed', text: a[i - 1] })
      i--
    }
  }
  return result.reverse()
}

function mergeAdjacent(segments) {
  if (!segments.length) return []
  const merged = [segments[0]]
  for (let i = 1; i < segments.length; i++) {
    const last = merged[merged.length - 1]
    if (last.type === segments[i].type) {
      last.text += segments[i].text
    } else {
      merged.push(segments[i])
    }
  }
  return merged
}

export function computeDiff(oldText, newText) {
  const a = oldText || ''
  const b = newText || ''
  if (a === b) return [{ type: 'same', text: b || '(空)' }]
  if (!a) return [{ type: 'added', text: b }]
  if (!b) return [{ type: 'removed', text: a }]
  const dp = lcs(a, b)
  const segments = backtrack(dp, a, b, a.length, b.length)
  return mergeAdjacent(segments)
}
