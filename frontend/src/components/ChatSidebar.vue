<template>
  <div class="cs-sidebar">
    <button class="cs-new-btn" @click="$emit('newChat')">
      <PlusCircle class="icon-sm" /> 新对话
    </button>

    <div class="cs-list">
      <div v-if="sessions.length === 0" class="cs-empty">
        暂无对话记录
      </div>
      <div
        v-for="s in sessions"
        :key="s.id"
        :class="['cs-item', { active: s.id === activeId }]"
        @click="$emit('select', s.id)"
      >
        <div class="cs-item-main">
          <MessageCircle class="cs-item-icon" />
          <div class="cs-item-text">
            <span class="cs-item-title">{{ s.title || '新对话' }}</span>
            <span class="cs-item-meta">
              {{ s.message_count }} 条消息
            </span>
          </div>
        </div>
        <button class="cs-del-btn" @click.stop="$emit('delete', s.id)" title="删除">
          <Trash2 class="icon-xs" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { MessageCircle, PlusCircle, Trash2 } from 'lucide-vue-next'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})
defineEmits(['newChat', 'select', 'delete'])
</script>

<style scoped>
.cs-sidebar {
  width: 260px;
  min-width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e8e6dc;
  background: #fafaf8;
  overflow: hidden;
}
.cs-new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 12px;
  padding: 10px;
  border: 1.5px dashed #d0cdc0;
  border-radius: 10px;
  background: transparent;
  color: #5e5d59;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.cs-new-btn:hover {
  border-color: #c96442;
  color: #c96442;
  background: #fdf8f5;
}
.cs-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}
.cs-empty {
  text-align: center;
  color: #b8b4aa;
  font-size: 13px;
  padding: 24px 0;
}
.cs-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}
.cs-item:hover {
  background: #f5f2eb;
}
.cs-item.active {
  background: #fdf8f5;
  border: 1px solid #f0d4c8;
}
.cs-item-main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.cs-item-icon {
  width: 16px;
  height: 16px;
  color: #b8b4aa;
  flex-shrink: 0;
  margin-top: 2px;
}
.cs-item-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cs-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #3d3d3a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cs-item-meta {
  font-size: 11px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 4px;
}
.cs-del-btn {
  border: none;
  background: transparent;
  color: #ccc;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.15s;
}
.cs-item:hover .cs-del-btn {
  opacity: 1;
}
.cs-del-btn:hover {
  color: #e07a5f;
  background: #fef0ec;
}
</style>
