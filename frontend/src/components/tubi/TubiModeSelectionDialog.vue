<template>
  <el-dialog
    v-model="localVisible"
    title="选择处理方式"
    width="700px"
    :close-on-click-modal="false"
    class="modern-form-dialog mode-selection-dialog"
    :before-close="handleClose"
  >
    <div class="mode-selection-container">
      <div class="mode-cards-grid">
        <!-- 直接入库 -->
        <div
          class="mode-card"
          :class="{ 'selected': localMode === 'manual' }"
          @click="selectMode('manual')"
        >
          <div class="mode-icon">
            <el-icon size="40"><Folder /></el-icon>
          </div>
          <div class="mode-title">直接入库</div>
          <div class="mode-desc">仅录入不分析，后续可手动标注</div>
        </div>

        <!-- AI文本分析 -->
        <div
          class="mode-card"
          :class="{ 'selected': localMode === 'analyze_text_only' }"
          @click="selectMode('analyze_text_only')"
        >
          <div class="mode-icon highlight">
            <el-icon size="40"><Document /></el-icon>
          </div>
          <div class="mode-title">AI文本分析</div>
          <div class="mode-desc">轻量化快速点评概述</div>
        </div>

        <!-- AI标注图分析 -->
        <div
          class="mode-card"
          :class="{ 'selected': localMode === 'analyze' }"
          @click="selectMode('analyze')"
        >
          <div class="mode-icon">
            <el-icon size="40"><Brush /></el-icon>
          </div>
          <div class="mode-title">AI标注图分析</div>
          <div class="mode-desc">完整分析（含区域检测+OCR+标注图）</div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer modern-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button
          type="primary"
          @click="confirmMode"
          :disabled="!localMode"
        >
          确认选择
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Folder, Document, Brush } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  defaultMode: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const localVisible = ref(props.modelValue)
const localMode = ref(props.defaultMode)

watch(() => props.modelValue, (val) => {
  localVisible.value = val
  if (!val) {
    localMode.value = null
  }
})

watch(localVisible, (val) => {
  emit('update:modelValue', val)
})

function selectMode(mode) {
  localMode.value = mode
}

function confirmMode() {
  if (localMode.value) {
    emit('confirm', localMode.value)
    localVisible.value = false
  }
}

function handleClose() {
  emit('cancel')
  localVisible.value = false
}
</script>

<style scoped>
.mode-selection-container {
  padding: 16px 0;
}

.mode-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.mode-card {
  border: 2px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 24px 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
}

.mode-card:hover {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.mode-card.selected {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-7);
}

.mode-icon {
  margin-bottom: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  justify-content: center;
}

.mode-icon.highlight {
  color: var(--el-color-primary);
}

.mode-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.mode-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
</style>
