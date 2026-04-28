<template>
  <div class="markdown-viewer">
    <div class="md-header">
      <FileCode class="icon" />
      <span>Markdown 视图</span>
      <button class="md-copy-btn" @click="copyMarkdown" title="复制 Markdown">
        <Copy class="icon" />
      </button>
    </div>
    
    <div v-if="loading" class="md-loading">
      <Loader2 class="icon spin" />
      <span>加载中...</span>
    </div>
    
    <div v-else-if="!markdown" class="md-empty">
      <FileText class="icon" />
      <span>暂无 Markdown 内容</span>
    </div>
    
    <div v-else class="md-content" v-html="renderedHtml"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { FileCode, FileText, Copy, Loader2 } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'

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

// 简易 Markdown → HTML 转换
const renderedHtml = computed(() => {
  if (!props.markdown) return ''
  return simpleMarkdownToHtml(props.markdown)
})

function simpleMarkdownToHtml(md) {
  let html = md
    // 标题
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 行内代码
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // 图片
    .replace(/!\[(.+?)\]\((.+?)\)/g, '<img src="$2" alt="$1" class="md-image" />')
    // 链接
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>')
    // 水平线
    .replace(/^---$/gm, '<hr />')
    // 无序列表
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // 段落（双换行）
    .replace(/\n\n/g, '</p><p>')
    // 单换行
    .replace(/\n/g, '<br />')
  
  // 包裹 li
  html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
  // 清理空段落
  html = html.replace(/<p><\/p>/g, '')
  // 包裹整体
  html = '<p>' + html + '</p>'
  
  return html
}

function copyMarkdown() {
  if (!props.markdown) return
  navigator.clipboard.writeText(props.markdown).then(() => {
    ElMessage.success('Markdown 已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
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
  max-height: 500px;
}

/* Markdown 渲染样式 */
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

.md-content :deep(p) {
  margin: 8px 0;
}

.md-content :deep(strong) {
  font-weight: 600;
  color: #141413;
}

.md-content :deep(em) {
  font-style: italic;
  color: #5a5a5a;
}

.md-content :deep(code) {
  background: #f5f0e8;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  color: #c45c48;
}

.md-content :deep(a) {
  color: #c45c48;
  text-decoration: none;
}

.md-content :deep(a:hover) {
  text-decoration: underline;
}

.md-content :deep(hr) {
  border: none;
  border-top: 1px solid #e8e4dc;
  margin: 20px 0;
}

.md-content :deep(ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.md-content :deep(li) {
  margin: 4px 0;
}

.md-content :deep(.md-image) {
  max-width: 100%;
  border-radius: 6px;
  margin: 12px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

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
