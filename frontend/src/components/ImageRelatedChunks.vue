<template>
  <div class="image-related-chunks">
    <div class="related-header">
      <Link class="icon" />
      <span>{{ $t('c-imagerelatedchunks.t1') }}</span>
      <span v-if="chunks.length" class="related-count">{{ chunks.length }}</span>
    </div>
    
    <div v-if="loading" class="related-loading">
      <Loader2 class="icon spin" />
      <span>{{ $t('common.loading') }}</span>
    </div>
    
    <div v-else-if="!chunks.length" class="related-empty">
      <Unlink class="icon" />
      <span>{{ $t('c-imagerelatedchunks.t2') }}</span>
    </div>
    
    <div v-else class="related-list">
      <div 
        v-for="(chunk, index) in chunks" 
        :key="chunk.id || index"
        class="related-item"
        @click="$emit('chunk-click', chunk)"
      >
        <div class="item-header">
          <span class="item-index">#{{ index + 1 }}</span>
          <span v-if="chunk.page_start" class="item-page">第 {{ chunk.page_start }} 页</span>
          <span v-if="chunk.chapter_title" class="item-chapter">{{ chunk.chapter_title }}</span>
        </div>
        <div class="item-content">
          {{ truncateText(chunk.content, 150) }}
        </div>
        <div v-if="chunk.score" class="item-score">
          相关度 {{ formatScore(chunk.score) }}%
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Link, Unlink, Loader2 } from 'lucide-vue-next'

const props = defineProps({
  // 关联文本块数组
  chunks: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['chunk-click'])

function truncateText(text, maxLen) {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

function formatScore(score) {
  if (!score || score <= 0) return 0
  if (score < 0.1) return Math.round(Math.min(score / 0.05, 1) * 100)
  if (score < 0.3) return Math.max(20, Math.round(Math.min((score - 0.05) / 0.25, 1) * 100))
  if (score > 1) return Math.min(Math.round(score), 100)
  return Math.round(score * 100)
}
</script>

<style scoped>
.image-related-chunks {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e8e4dc;
  overflow: hidden;
}

.related-header {
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

.related-count {
  padding: 2px 8px;
  background: #e8e4dc;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: #8b7355;
}

.related-loading,
.related-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  gap: 8px;
  color: #8b7355;
  font-size: 13px;
}

.related-list {
  overflow-y: auto;
  max-height: 400px;
}

.related-item {
  padding: 14px 16px;
  border-bottom: 1px solid #f0ede5;
  cursor: pointer;
  transition: all 0.15s;
}

.related-item:last-child {
  border-bottom: none;
}

.related-item:hover {
  background: #faf9f7;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.item-index {
  font-size: 12px;
  font-weight: 600;
  color: #c45c48;
  background: #fef3c7;
  padding: 2px 8px;
  border-radius: 4px;
}

.item-page {
  font-size: 12px;
  color: #8b7355;
}

.item-chapter {
  font-size: 12px;
  color: #5a5a5a;
  background: #f5f0e8;
  padding: 2px 8px;
  border-radius: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-content {
  font-size: 13px;
  line-height: 1.6;
  color: #5a5a5a;
  margin-bottom: 8px;
}

.item-score {
  font-size: 11px;
  color: #16a34a;
  font-weight: 500;
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
