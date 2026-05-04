<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <!-- 头部 -->
        <div class="modal-header">
          <div class="header-info">
            <span class="chapter-tag">{{ result.chapter_title || '未分类' }}</span>
            <span class="page-info">第 {{ result.page_start }}-{{ result.page_end }} 页</span>
          </div>
          <button class="close-btn" @click="closeModal">
            <X class="icon" />
          </button>
        </div>

        <!-- 主体内容 -->
        <div class="modal-body">
          <!-- 关联图片 -->
          <div v-if="result.associated_images?.length > 0" class="images-section">
            <h3 class="section-title">
              <ImageIcon class="section-icon" />
              关联插图 ({{ result.associated_images.length }})
            </h3>
            <div class="images-grid">
              <div 
                v-for="img in result.associated_images" 
                :key="img.id"
                class="image-item"
                @click="previewImage(img)"
              >
                <img :src="getImageUrl(img)" :alt="img.display_label || img.figure_id || '插图'" />
                <span v-if="img.display_label || img.figure_id" class="image-label">{{ img.display_label || img.figure_id }}</span>
              </div>
            </div>
          </div>

          <!-- 文本内容 -->
          <div class="content-section">
            <h3 class="section-title">
              <FileText class="section-icon" />
              文本内容
            </h3>
            
            <!-- 上文 -->
            <div v-if="result.context_before" class="context-before">
              <p class="context-text">{{ result.context_before }}</p>
              <div class="context-divider">
                <span class="divider-line"></span>
                <span class="divider-text">上文</span>
                <span class="divider-line"></span>
              </div>
            </div>

            <!-- 当前内容 -->
            <div class="main-content">
              <p class="content-text">{{ result.content }}</p>
            </div>

            <!-- 下文 -->
            <div v-if="result.context_after" class="context-after">
              <div class="context-divider">
                <span class="divider-line"></span>
                <span class="divider-text">下文</span>
                <span class="divider-line"></span>
              </div>
              <p class="context-text">{{ result.context_after }}</p>
            </div>
          </div>

          <!-- 来源信息 -->
          <div class="source-section">
            <div class="source-info">
              <BookOpen class="source-icon" />
              <span class="source-book">{{ result.book_title }}</span>
            </div>
            <div class="score-badge">
              相关度: {{ (result.score * 100).toFixed(1) }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图片预览 -->
    <div v-if="previewVisible" class="image-preview-overlay" @click="previewVisible = false">
      <img :src="previewImageUrl" class="preview-image" />
      <button class="preview-close" @click="previewVisible = false">
        <X class="icon" />
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { X, ImageIcon, FileText, BookOpen } from 'lucide-vue-next'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  result: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:visible'])

const previewVisible = ref(false)
const previewImageUrl = ref('')

function closeModal() {
  emit('update:visible', false)
}

function getImageUrl(img) {
  if (img.stored_url?.startsWith('http')) {
    return img.stored_url
  }
  if (/^[a-f0-9-]{36}$/.test(img.stored_url || '')) {
    return `/api/v1/knowledge/images/${img.stored_url}`
  }
  return `${(img.stored_url || '').replace('/api/knowledge', '/api/v1/knowledge')}`
}

function previewImage(img) {
  previewImageUrl.value = getImageUrl(img)
  previewVisible.value = true
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e8e4dc;
  background: #f8f6f1;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chapter-tag {
  padding: 6px 14px;
  background: #c45c48;
  color: #fff;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.page-info {
  font-size: 14px;
  color: #8b7355;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 8px;
  color: #8b7355;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #fee2e2;
  border-color: #ef4444;
  color: #ef4444;
}

.icon {
  width: 20px;
  height: 20px;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* 图片区域 */
.images-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #3d3d3d;
  margin-bottom: 16px;
}

.section-icon {
  width: 20px;
  height: 20px;
  color: #c45c48;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

.image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid #e8e4dc;
  transition: all 0.2s;
}

.image-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.image-item img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fafaf8;
}

.image-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  text-align: center;
}

/* 内容区域 */
.content-section {
  background: #f8f6f1;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.context-before,
.context-after {
  opacity: 0.6;
}

.context-text {
  font-size: 14px;
  line-height: 1.8;
  color: #5a5a5a;
  font-style: italic;
}

.context-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: #d4cfc5;
}

.divider-text {
  font-size: 12px;
  color: #8b7355;
  font-weight: 500;
}

.main-content {
  padding: 16px 0;
}

.content-text {
  font-size: 16px;
  line-height: 2;
  color: #3d3d3d;
  text-align: justify;
}

/* 来源信息 */
.source-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #e8e4dc;
  border-radius: 10px;
}

.source-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.source-icon {
  width: 18px;
  height: 18px;
  color: #8b7355;
}

.source-book {
  font-size: 14px;
  color: #5a5a5a;
}

.score-badge {
  padding: 6px 14px;
  background: #dcfce7;
  color: #16a34a;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

/* 图片预览 */
.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.preview-image {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
}

.preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.preview-close:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
