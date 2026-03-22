<template>
  <div class="stele-detail-page">
    <el-page-header @back="goBack" title="返回列表" />
    
    <div v-if="stele" class="detail-content">
      <!-- 碑帖基本信息 -->
      <el-card shadow="hover" class="info-card">
        <div class="stele-header">
          <h1 class="stele-title">{{ stele.name }}</h1>
          <el-tag :type="getStyleType(stele.style)" size="large">{{ stele.style }}</el-tag>
        </div>
        
        <el-descriptions :column="3" border class="stele-meta">
          <el-descriptions-item label="书法家">
            <el-icon><User /></el-icon> {{ stele.calligrapher }}
          </el-descriptions-item>
          <el-descriptions-item label="朝代">
            <el-icon><Calendar /></el-icon> {{ stele.dynasty }}
          </el-descriptions-item>
          <el-descriptions-item label="字形数量">
            <el-icon><Document /></el-icon> {{ totalCharacters }} 字
          </el-descriptions-item>
        </el-descriptions>
        
        <div class="stele-description">
          <h3>简介</h3>
          <p>{{ stele.description }}</p>
        </div>
      </el-card>

      <!-- 字形展示 -->
      <el-card shadow="hover" class="characters-card">
        <template #header>
          <div class="card-header">
            <span>字形库</span>
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="totalCharacters"
              :page-sizes="[20, 40, 60]"
              layout="total, sizes, prev, pager, next"
              small
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </template>

        <div class="characters-grid" v-loading="loading">
          <div
            v-for="char in characters"
            :key="char.id"
            class="character-item"
          >
            <div class="character-image">
              <img v-if="char.image_path" :src="char.image_path" :alt="char.character">
              <span v-else class="character-text">{{ char.character }}</span>
            </div>
            <div class="character-info">
              <span class="char-name">{{ char.character }}</span>
              <span class="char-unicode">{{ char.unicode }}</span>
            </div>
          </div>
        </div>

        <el-empty v-if="!loading && characters.length === 0" description="暂无字形数据" />
      </el-card>
    </div>

    <el-skeleton v-else :rows="10" animated />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, Calendar, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { steleApi } from '../api'

const route = useRoute()
const router = useRouter()

const stele = ref(null)
const characters = ref([])
const loading = ref(false)
const totalCharacters = ref(0)
const currentPage = ref(1)
const pageSize = ref(40)

// 获取碑帖详情
const fetchSteleDetail = async () => {
  const id = route.params.id
  
  try {
    const response = await steleApi.getStele(id)
    if (response.success) {
      stele.value = response.data
    }
  } catch (error) {
    console.error('获取碑帖详情失败:', error)
    ElMessage.error('获取碑帖详情失败')
  }
}

// 获取字形列表
const fetchCharacters = async () => {
  const id = route.params.id
  loading.value = true
  
  try {
    const response = await steleApi.getSteleCharacters(id, {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    })
    
    if (response.success) {
      characters.value = response.data.characters
      totalCharacters.value = response.data.total
    }
  } catch (error) {
    console.error('获取字形列表失败:', error)
    ElMessage.error('获取字形列表失败')
  } finally {
    loading.value = false
  }
}

// 获取风格标签类型
const getStyleType = (style) => {
  const typeMap = {
    '楷书': 'success',
    '行书': 'primary',
    '草书': 'warning',
    '隶书': 'danger',
    '篆书': 'info'
  }
  return typeMap[style] || ''
}

// 返回列表
const goBack = () => {
  router.push('/steles')
}

// 处理分页
const handleSizeChange = (size) => {
  pageSize.value = size
  fetchCharacters()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  fetchCharacters()
}

onMounted(() => {
  fetchSteleDetail()
  fetchCharacters()
})
</script>

<style scoped>
.stele-detail-page {
  padding: 20px 0;
}

.detail-content {
  margin-top: 20px;
}

.info-card {
  margin-bottom: 30px;
}

.stele-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.stele-title {
  font-size: 32px;
  margin: 0;
  color: #333;
}

.stele-meta {
  margin-bottom: 20px;
}

.stele-description {
  margin-top: 20px;
}

.stele-description h3 {
  margin-bottom: 10px;
  color: #333;
}

.stele-description p {
  line-height: 1.8;
  color: #666;
  white-space: pre-line;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.characters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 15px;
}

.character-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.3s;
}

.character-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.character-image {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}

.character-image img {
  max-width: 80%;
  max-height: 80%;
  object-fit: contain;
}

.character-text {
  font-size: 48px;
  font-family: "KaiTi", "STKaiti", serif;
  color: #333;
}

.character-info {
  padding: 10px;
  text-align: center;
  background: #fff;
}

.char-name {
  display: block;
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 5px;
}

.char-unicode {
  display: block;
  font-size: 12px;
  color: #909399;
}
</style>
