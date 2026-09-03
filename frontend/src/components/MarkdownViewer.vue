<template>
  <div class="markdown-viewer">
    <div class="md-header">
      <FileCode class="icon" />
      <span>{{ $t('c-markdownviewer.t1') }}</span>
      <button class="md-copy-btn" @click="copyMarkdown" :title="$t('c-markdownviewer.a1')">
        <Copy class="icon" />
      </button>
    </div>
    
    <div v-if="loading" class="md-loading">
      <Loader2 class="icon spin" />
      <span>{{ $t('common.loading') }}</span>
    </div>
    
    <div v-else-if="!markdown" class="md-empty">
      <FileText class="icon" />
      <span>{{ $t('c-markdownviewer.t2') }}</span>
    </div>
    
    <div v-else class="md-content" v-html="$sanitize(renderedHtml)"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { FileCode, FileText, Copy, Loader2 } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { translate as t } from '@/locales'

const props = defineProps({
  markdown: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Markdown → HTML 转换（支持表格、代码块、引用、列表）
const renderedHtml = computed(() => {
  if (!props.markdown) return ''
  return markdownToHtml(props.markdown)
})

function markdownToHtml(md) {
  // 预处理：保护代码块和行内代码
  const codeBlocks = []
  const inlineCodes = []
  
  // 提取代码块（```...```）
  let processed = md.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const index = codeBlocks.length
    codeBlocks.push({ lang, code: escapeHtml(code.trim()) })
    return `\n%%CODEBLOCK_${index}%%\n`
  })
  
  // 提取行内代码（`...`）
  processed = processed.replace(/`([^`\n]+)`/g, (match, code) => {
    const index = inlineCodes.length
    inlineCodes.push(escapeHtml(code))
    return `%%INLINECODE_${index}%%`
  })
  
  // 按行处理
  const lines = processed.split('\n')
  const htmlParts = []
  let i = 0
  let inTable = false
  let tableRows = []
  let inList = false
  let listType = ''
  let listItems = []
  
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()
    
    // 代码块占位符
    const codeBlockMatch = trimmed.match(/^%%CODEBLOCK_(\d+)%%$/)
    if (codeBlockMatch) {
      const block = codeBlocks[parseInt(codeBlockMatch[1])]
      const langClass = block.lang ? ` class="language-${block.lang}"` : ''
      htmlParts.push(`<pre class="md-code-block"><code${langClass}>${block.code}</code></pre>`)
      i++
      continue
    }
    
    // 空行 - 结束当前列表或表格
    if (!trimmed) {
      if (inList) {
        htmlParts.push(closeList(listType, listItems))
        inList = false
        listItems = []
      }
      if (inTable) {
        htmlParts.push(buildTable(tableRows))
        inTable = false
        tableRows = []
      }
      i++
      continue
    }
    
    // 表格行（| ... | ... |）
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      // 跳过分隔行（|---|---|）
      if (/^\|[\s\-:|]+\|$/.test(trimmed)) {
        i++
        continue
      }
      
      const cells = trimmed.split('|').slice(1, -1).map(c => c.trim())
      
      if (!inTable) {
        inTable = true
        tableRows = []
      }
      
      tableRows.push(cells)
      i++
      continue
    } else if (inTable) {
      // 表格结束
      htmlParts.push(buildTable(tableRows))
      inTable = false
      tableRows = []
    }
    
    // 标题
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      if (inList) {
        htmlParts.push(closeList(listType, listItems))
        inList = false
        listItems = []
      }
      const level = headingMatch[1].length
      const text = restoreInlineCode(headingMatch[2], inlineCodes)
      htmlParts.push(`<h${level}>${text}</h${level}>`)
      i++
      continue
    }
    
    // 引用块（> ...）
    if (trimmed.startsWith('>')) {
      if (inList) {
        htmlParts.push(closeList(listType, listItems))
        inList = false
        listItems = []
      }
      
      // 收集连续的引用行
      const quoteLines = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      const quoteText = restoreInlineCode(quoteLines.join('\n'), inlineCodes)
      htmlParts.push(`<blockquote class="md-blockquote">${markdownToHtml(quoteText)}</blockquote>`)
      continue
    }
    
    // 水平线
    if (/^[-*_]{3,}$/.test(trimmed)) {
      if (inList) {
        htmlParts.push(closeList(listType, listItems))
        inList = false
        listItems = []
      }
      htmlParts.push('<hr />')
      i++
      continue
    }
    
    // 无序列表
    const ulMatch = trimmed.match(/^[-*+]\s+(.+)$/)
    if (ulMatch) {
      if (!inList || listType !== 'ul') {
        if (inList) {
          htmlParts.push(closeList(listType, listItems))
        }
        inList = true
        listType = 'ul'
        listItems = []
      }
      listItems.push(restoreInlineCode(ulMatch[1], inlineCodes))
      i++
      continue
    }
    
    // 有序列表
    const olMatch = trimmed.match(/^\d+[.)]\s+(.+)$/)
    if (olMatch) {
      if (!inList || listType !== 'ol') {
        if (inList) {
          htmlParts.push(closeList(listType, listItems))
        }
        inList = true
        listType = 'ol'
        listItems = []
      }
      listItems.push(restoreInlineCode(olMatch[1], inlineCodes))
      i++
      continue
    }
    
    // 普通段落
    if (inList) {
      htmlParts.push(closeList(listType, listItems))
      inList = false
      listItems = []
    }
    
    // 处理行内格式
    let paragraphText = restoreInlineCode(trimmed, inlineCodes)
    paragraphText = applyInlineFormatting(paragraphText)
    htmlParts.push(`<p>${paragraphText}</p>`)
    i++
  }
  
  // 关闭未结束的列表或表格
  if (inList) {
    htmlParts.push(closeList(listType, listItems))
  }
  if (inTable) {
    htmlParts.push(buildTable(tableRows))
  }
  
  return htmlParts.join('\n')
}

// HTML 转义
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// 恢复行内代码占位符
function restoreInlineCode(text, inlineCodes) {
  return text.replace(/%%INLINECODE_(\d+)%%/g, (match, index) => {
    return `<code class="md-inline-code">${inlineCodes[parseInt(index)]}</code>`
  })
}

// 应用行内格式
function applyInlineFormatting(text) {
  return text
    // 粗体 **...** 或 __...__
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    // 斜体 *...* 或 _..._
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    // 删除线 ~~...~~
    .replace(/~~(.+?)~~/g, '<del>$1</del>')
    // 图片 ![alt](src)
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="md-image" />')
    // 链接 [text](url)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
}

// 构建表格 HTML
function buildTable(rows) {
  if (rows.length === 0) return ''
  
  // 第一行是表头
  const headerCells = rows[0]
  const bodyRows = rows.slice(1)
  
  let html = '<div class="md-table-wrapper"><table class="md-table">'
  
  // 表头
  html += '<thead><tr>'
  headerCells.forEach(cell => {
    html += `<th>${applyInlineFormatting(restoreInlineCode(cell, []))}</th>`
  })
  html += '</tr></thead>'
  
  // 表体
  if (bodyRows.length > 0) {
    html += '<tbody>'
    bodyRows.forEach(row => {
      html += '<tr>'
      row.forEach(cell => {
        html += `<td>${applyInlineFormatting(restoreInlineCode(cell, []))}</td>`
      })
      html += '</tr>'
    })
    html += '</tbody>'
  }
  
  html += '</table></div>'
  return html
}

// 关闭列表
function closeList(type, items) {
  if (items.length === 0) return ''
  const tag = type
  const itemsHtml = items.map(item => `<li>${applyInlineFormatting(item)}</li>`).join('\n')
  return `<${tag}>${itemsHtml}</${tag}>`
}

function copyMarkdown() {
  if (!props.markdown) return
  navigator.clipboard.writeText(props.markdown).then(() => {
    ElMessage.success(t('c-markdownviewer.s1'))
  }).catch(() => {
    ElMessage.error(t('c-bookreadermodal.s2'))
  })
}
</script>

<style scoped>
.markdown-viewer {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e8e4dc;
  overflow: hidden;
}

.md-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #faf9f7;
  border-bottom: 1px solid #e8e4dc;
  font-size: 14px;
  font-weight: 600;
  color: #3d3d3d;
}

.md-copy-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.md-copy-btn:hover {
  background: #c45c48;
  border-color: #c45c48;
  color: #fff;
}

.md-loading,
.md-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  gap: 8px;
  color: #8b7355;
  font-size: 13px;
}

.md-content {
  padding: 20px 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #3d3d3d;
  overflow-y: auto;
  max-height: 600px;
}

/* 标题 */
.md-content :deep(h1) {
  font-size: 22px;
  font-weight: 700;
  color: #141413;
  margin: 24px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e8e4dc;
}

.md-content :deep(h2) {
  font-size: 18px;
  font-weight: 600;
  color: #3d3d3d;
  margin: 20px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e4dc;
}

.md-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: #5a5a5a;
  margin: 16px 0 8px;
}

.md-content :deep(h4),
.md-content :deep(h5),
.md-content :deep(h6) {
  font-size: 14px;
  font-weight: 600;
  color: #5a5a5a;
  margin: 12px 0 6px;
}

/* 段落 */
.md-content :deep(p) {
  margin: 8px 0;
}

/* 粗体、斜体 */
.md-content :deep(strong) {
  font-weight: 600;
  color: #141413;
}

.md-content :deep(em) {
  font-style: italic;
  color: #5a5a5a;
}

.md-content :deep(del) {
  text-decoration: line-through;
  color: #999;
}

/* 行内代码 */
.md-content :deep(.md-inline-code),
.md-content :deep(code:not(.md-inline-code):not([class^="language-"])) {
  background: #f5f0e8;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: #c45c48;
}

/* 代码块 */
.md-content :deep(.md-code-block) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px 20px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 16px 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.md-content :deep(.md-code-block code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

.md-content :deep(.md-code-block .language-python),
.md-content :deep(.md-code-block .language-py) {
  color: #d4d4d4;
}

/* 引用块 */
.md-content :deep(.md-blockquote) {
  margin: 16px 0;
  padding: 12px 20px;
  border-left: 4px solid #c45c48;
  background: #faf9f7;
  border-radius: 0 8px 8px 0;
  color: #5a5a5a;
  font-style: italic;
}

.md-content :deep(.md-blockquote p) {
  margin: 4px 0;
}

/* 链接 */
.md-content :deep(a) {
  color: #c45c48;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}

.md-content :deep(a:hover) {
  border-bottom-color: #c45c48;
}

/* 水平线 */
.md-content :deep(hr) {
  border: none;
  border-top: 1px solid #e8e4dc;
  margin: 20px 0;
}

/* 列表 */
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.md-content :deep(li) {
  margin: 4px 0;
}

.md-content :deep(ul li::marker) {
  color: #c45c48;
}

.md-content :deep(ol li::marker) {
  color: #c45c48;
  font-weight: 600;
}

/* 表格 */
.md-content :deep(.md-table-wrapper) {
  overflow-x: auto;
  margin: 16px 0;
  border-radius: 8px;
  border: 1px solid #e8e4dc;
}

.md-content :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.md-content :deep(.md-table th) {
  background: #faf9f7;
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  color: #3d3d3d;
  border-bottom: 2px solid #e8e4dc;
  white-space: nowrap;
}

.md-content :deep(.md-table td) {
  padding: 8px 14px;
  border-bottom: 1px solid #e8e4dc;
  color: #5a5a5a;
}

.md-content :deep(.md-table tr:last-child td) {
  border-bottom: none;
}

.md-content :deep(.md-table tr:hover td) {
  background: #faf9f7;
}

/* 图片 */
.md-content :deep(.md-image) {
  max-width: 100%;
  border-radius: 6px;
  margin: 12px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 图标 */
.icon {
  width: 16px;
  height: 16px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
