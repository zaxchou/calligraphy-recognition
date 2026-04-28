<template>
  <div class="table-result-card" @click="$emit('click')">
    <div class="card-header">
      <div class="card-type">
        <Table class="icon" />
        <span>表格</span>
      </div>
      <span class="card-score" :class="scoreClass">
        {{ formattedScore }}%
      </span>
    </div>
    
    <div class="card-body">
      <div class="card-title" v-if="result.chapter_title">
        {{ cleanLatex(result.chapter_title) }}
      </div>
      
      <!-- 表格内容预览 -->
      <div class="table-preview" v-html="tablePreviewHtml"></div>
      
      <div class="card-meta">
        <span v-if="result.book_title" class="meta-item">
          <BookOpen class="meta-icon" />
          {{ cleanLatex(result.book_title) }}
        </span>
        <span v-if="result.page_start" class="meta-item">
          <FileText class="meta-icon" />
          第 {{ result.page_start }} 页
        </span>
        <span v-if="result.table_index != null" class="meta-item">
          <Hash class="meta-icon" />
          表 {{ result.table_index + 1 }}
        </span>
      </div>
    </div>
    
    <div class="card-footer">
      <span class="footer-hint">点击查看完整内容</span>
      <ChevronRight class="footer-icon" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Table, BookOpen, FileText, Hash, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

defineEmits(['click'])

// 格式化分数
const formattedScore = computed(() => {
  const score = props.result.score
  if (!score || score <= 0) return 0
  if (score < 0.1) return Math.round(Math.min(score / 0.05, 1) * 100)
  if (score < 0.3) return Math.max(20, Math.round(Math.min((score - 0.05) / 0.25, 1) * 100))
  if (score > 1) return Math.min(Math.round(score), 100)
  return Math.round(score * 100)
})

const scoreClass = computed(() => {
  const s = formattedScore.value
  if (s >= 80) return 'high'
  if (s >= 50) return 'medium'
  return 'low'
})

// 表格内容预览（取前几行）
const tablePreviewHtml = computed(() => {
  const content = props.result.content || ''
  if (!content) return '<span class="empty-hint">暂无内容</span>'
  
  // 如果是 Markdown 表格格式，取前 5 行
  const lines = content.split('\n').filter(l => l.trim())
  const previewLines = lines.slice(0, 5)
  let html = previewLines.map(line => {
    // 简单的 Markdown 表格行渲染
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line.split('|').filter(c => c.trim())
      if (cells.some(c => /^[-:]+$/.test(c.trim()))) {
        return '' // 跳过分隔行
      }
      return '<div class="table-row">' + cells.map(c => `<span class="table-cell">${cleanLatex(c.trim())}</span>`).join('') + '</div>'
    }
    return `<div class="table-text">${cleanLatex(line)}</div>`
  }).filter(Boolean).join('')
  
  if (lines.length > 5) {
    html += `<div class="table-more">... 共 ${lines.length} 行</div>`
  }
  
  return html
})

function cleanLatex(text) {
  if (!text) return ''
  const circledMap = {
    '0': '⓪', '1': '①', '2': '②', '3': '③', '4': '④',
    '5': '⑤', '6': '⑥', '7': '⑦', '8': '⑧', '9': '⑨',
    '10': '⑩', '11': '⑪', '12': '⑫', '13': '⑬', '14': '⑭',
    '15': '⑮', '16': '⑯', '17': '⑰', '18': '⑱', '19': '⑲',
    '20': '⑳'
  }
  return text.replace(/\$\\textcircled\{(\d+)\}\$/g, (m, n) => circledMap[n] || `(${n})`)
}
</script>

<style scoped>
.table-result-card {
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.table-result-card:hover {
  border-color: #c45c48;
  box-shadow: 0 4px 16px rgba(196, 92, 72, 0.15);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #faf9f7;
  border-bottom: 1px solid #e8e4dc;
}

.card-type {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #8b7355;
}

.card-score {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.card-score.high {
  background: #dcfce7;
  color: #166534;
}

.card-score.medium {
  background: #fef9c3;
  color: #854d0e;
}

.card-score.low {
  background: #fee2e2;
  color: #991b1b;
}

.card-body {
  padding: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #3d3d3d;
  margin-bottom: 12px;
}

.table-preview {
  background: #faf9f7;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
  overflow: hidden;
  max-height: 150px;
}

.table-preview :deep(.table-row) {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #f0ede5;
}

.table-preview :deep(.table-row:last-child) {
  border-bottom: none;
}

.table-preview :deep(.table-cell) {
  flex: 1;
  font-size: 12px;
  color: #5a5a5a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-preview :deep(.table-text) {
  font-size: 12px;
  color: #5a5a5a;
  padding: 2px 0;
}

.table-preview :deep(.table-more) {
  font-size: 11px;
  color: #8b7355;
  text-align: center;
  padding-top: 6px;
  border-top: 1px dashed #e8e4dc;
  margin-top: 6px;
}

.table-preview :deep(.empty-hint) {
  color: #b8a47e;
  font-size: 12px;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8b7355;
}

.meta-icon {
  width: 14px;
  height: 14px;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #faf9f7;
  border-top: 1px solid #e8e4dc;
}

.footer-hint {
  font-size: 12px;
  color: #b8a47e;
}

.footer-icon {
  width: 16px;
  height: 16px;
  color: #b8a47e;
}

.icon {
  width: 16px;
  height: 16px;
}
</style>
