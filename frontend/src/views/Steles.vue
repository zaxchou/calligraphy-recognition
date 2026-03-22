<template>
  <div class="steles-page">
    <h1 class="page-title">碑帖库</h1>
    
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-radio-group v-model="selectedStyle" @change="handleStyleChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="楷书">楷书</el-radio-button>
        <el-radio-button label="行书">行书</el-radio-button>
        <el-radio-button label="草书">草书</el-radio-button>
        <el-radio-button label="隶书">隶书</el-radio-button>
        <el-radio-button label="篆书">篆书</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 碑帖列表 -->
    <div class="steles-grid" v-loading="loading">
      <el-card
        v-for="stele in steles"
        :key="stele.id"
        class="stele-item"
        shadow="hover"
        @click="goToDetail(stele.id)"
      >
        <div class="stele-header">
          <h3 class="stele-name">{{ stele.name }}</h3>
          <el-tag :type="getStyleType(stele.style)">{{ stele.style }}</el-tag>
        </div>
        
        <div class="stele-meta">
          <p><el-icon><User /></el-icon> {{ stele.calligrapher }}</p>
          <p><el-icon><Calendar /></el-icon> {{ stele.dynasty }}</p>
        </div>
        
        <p class="stele-description">{{ stele.description }}</p>
        
        <div class="stele-footer">
          <el-button type="primary" text>
            查看详情
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-if="!loading && steles.length === 0" description="暂无碑帖数据" />

    <!-- 分页 -->
    <div class="pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[12, 24, 36]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Calendar, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { steleApi } from '../api'

const router = useRouter()

const steles = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const selectedStyle = ref('')

// 获取碑帖列表
const fetchSteles = async () => {
  loading.value = true
  
  try {
    const response = await steleApi.getSteles({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      style: selectedStyle.value || undefined
    })
    
    if (response.success) {
      steles.value = response.data
      total.value = response.total
    }
  } catch (error) {
    console.error('获取碑帖列表失败:', error)
    ElMessage.error('获取碑帖列表失败')
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

// 跳转到详情页
const goToDetail = (id) => {
  router.push(`/steles/${id}`)
}

// 处理风格筛选
const handleStyleChange = () => {
  currentPage.value = 1
  fetchSteles()
}

// 处理分页
const handleSizeChange = (size) => {
  pageSize.value = size
  fetchSteles()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  fetchSteles()
}

onMounted(() => {
  fetchSteles()
})
</script>

<style scoped>
.steles-page {
  padding: 20px 0;
}

.page-title {
  text-align: center;
  font-size: 32px;
  margin-bottom: 30px;
  color: #333;
}

.filter-bar {
  display: flex;
  justify-content: center;
  margin-bottom: 30px;
}

.steles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stele-item {
  cursor: pointer;
  transition: transform 0.3s;
}

.stele-item:hover {
  transform: translateY(-5px);
}

.stele-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.stele-name {
  font-size: 20px;
  margin: 0;
  color: #333;
}

.stele-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
  color: #666;
}

.stele-meta p {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
}

.stele-description {
  color: #666;
  line-height: 1.6;
  margin-bottom: 15px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stele-footer {
  text-align: right;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 30px;
}

/* 圆角胶囊按钮样式 */
:deep(.el-button) {
  border-radius: 50px;
  padding: 12px 32px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #ffa726 0%, #ff9800 100%);
  color: white;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #ffb74d 0%, #ffa726 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(255, 167, 38, 0.4);
}

:deep(.el-button--success) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--success:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--warning:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
  color: white;
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, #e57373 0%, #ef5350 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(239, 83, 80, 0.4);
}

:deep(.el-button--default) {
  background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
  color: #666;
}

:deep(.el-button--default:hover) {
  background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}

:deep(.el-button.is-small) {
  padding: 8px 20px;
  font-size: 13px;
}

:deep(.el-button.is-text) {
  background: transparent;
  box-shadow: none;
  color: #ff9800;
  padding: 8px 16px;
}

:deep(.el-button.is-text:hover) {
  background: rgba(255, 152, 0, 0.1);
  transform: none;
  box-shadow: none;
}
</style>
