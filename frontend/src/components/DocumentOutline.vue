<template>
  <div class="document-outline">
    <div class="outline-header">
      <ListTree class="icon" />
      <span>{{ $t('c-bookreadermodal.t6') }}</span>
      <span v-if="outline.length" class="outline-count">{{ outline.length }}</span>
    </div>
    
    <div v-if="loading" class="outline-loading">
      <Loader2 class="icon spin" />
      <span>{{ $t('c-documentoutline.t1') }}</span>
    </div>
    
    <div v-else-if="!outline.length" class="outline-empty">
      <FileText class="icon" />
      <span>{{ $t('c-documentoutline.t2') }}</span>
    </div>
    
    <div v-else class="outline-tree">
      <div 
        v-for="(item, index) in outline" 
        :key="index"
        class="outline-item"
        :class="[
          `level-${item.level || 1}`,
          { 'outline-active': activeIndex === index }
        ]"
        @click="onItemClick(item, index)"
      >
        <span class="outline-bullet" :class="`level-${item.level || 1}`"></span>
        <span class="outline-text">{{ item.title || item.text }}</span>
        <span v-if="item.page" class="outline-page">p.{{ item.page }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ListTree, FileText, Loader2 } from 'lucide-vue-next'

const props = defineProps({
  // 大纲数据数组 [{ title, level, page }]
  outline: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['item-click'])

const activeIndex = ref(-1)

function onItemClick(item, index) {
  activeIndex.value = index
  emit('item-click', {
    ...item,
    index
  })
}

// 监听 outline 变化，重置 active
watch(() => props.outline, () => {
  activeIndex.value = -1
})

defineExpose({
  setActiveIndex: (index) => { activeIndex.value = index }
})
</script>

<style scoped>
.document-outline {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e8e4dc;
  overflow: hidden;
}

.outline-header {
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

.outline-count {
  padding: 2px 8px;
  background: #e8e4dc;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: #8b7355;
}

.outline-loading,
.outline-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  gap: 8px;
  color: #8b7355;
  font-size: 13px;
}

.outline-tree {
  overflow-y: auto;
  max-height: 400px;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 3px solid transparent;
}

.outline-item:hover {
  background: #faf9f7;
}

.outline-item.outline-active {
  background: #fef3c7;
  border-left-color: #c45c48;
}

/* 层级缩进 */
.outline-item.level-1 {
  padding-left: 16px;
  font-weight: 600;
  font-size: 14px;
}

.outline-item.level-2 {
  padding-left: 32px;
  font-size: 13px;
}

.outline-item.level-3 {
  padding-left: 48px;
  font-size: 12px;
  color: #5a5a5a;
}

/* 层级圆点 */
.outline-bullet {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.outline-bullet.level-1 {
  background: #c45c48;
  width: 8px;
  height: 8px;
}

.outline-bullet.level-2 {
  background: #b8a47e;
}

.outline-bullet.level-3 {
  background: #d4cfc5;
}

.outline-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-page {
  font-size: 11px;
  color: #8b7355;
  background: #f5f0e8;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
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
