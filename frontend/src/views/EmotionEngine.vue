<template>
  <div class="emotion-engine-page">
    <div class="page-header">
      <h1>{{ $t('engine.title') }}</h1>
      <p class="page-subtitle">{{ $t('engine.subtitle') }}</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.lexicon?.total_words || 0 }}</div>
          <div class="stat-label">{{ $t('engine.lexicon_words') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.spatial_types || 0 }}</div>
          <div class="stat-label">{{ $t('engine.spatial_types') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.seal_rules || 0 }}</div>
          <div class="stat-label">{{ $t('engine.seal_rules') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.artist_baselines || 0 }}</div>
          <div class="stat-label">{{ $t('engine.artist_baselines') }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 词典管理 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('engine.lexicon_management') }}</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              :placeholder="$t('engine.search_word')"
              style="width: 200px; margin-right: 10px;"
              @keyup.enter="loadLexicon"
            />
            <el-select v-model="filterCategory" :placeholder="$t('engine.filter_category')" clearable style="width: 150px; margin-right: 10px;">
              <el-option label="negative_strong" value="negative_strong" />
              <el-option label="negative_moderate" value="negative_moderate" />
              <el-option label="negative_mild" value="negative_mild" />
              <el-option label="neutral" value="neutral" />
              <el-option label="positive_mild" value="positive_mild" />
              <el-option label="positive_moderate" value="positive_moderate" />
              <el-option label="positive_strong" value="positive_strong" />
            </el-select>
            <el-button type="primary" @click="loadLexicon">{{ $t('engine.search') }}</el-button>
            <el-button @click="showAddDialog = true">{{ $t('engine.add_word') }}</el-button>
          </div>
        </div>
      </template>

      <el-table :data="lexiconEntries" style="width: 100%" v-loading="loading">
        <el-table-column prop="word" :label="$t('engine.word')" width="150" />
        <el-table-column prop="score" :label="$t('engine.score')" width="100">
          <template #default="{ row }">
            <span :class="{ 'score-positive': row.score > 0, 'score-negative': row.score < 0 }">
              {{ row.score > 0 ? '+' : '' }}{{ row.score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="category" :label="$t('engine.category')" width="150" />
        <el-table-column prop="source" :label="$t('engine.source')" width="100" />
        <el-table-column prop="note" :label="$t('engine.note')" />
        <el-table-column :label="$t('engine.actions')" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="editWord(row)">{{ $t('engine.edit') }}</el-button>
            <el-button size="small" type="danger" @click="deleteWord(row.word)">{{ $t('engine.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalEntries"
        layout="total, prev, pager, next"
        @current-change="loadLexicon"
        style="margin-top: 20px; text-align: right;"
      />
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showAddDialog" :title="editingWord ? $t('engine.edit_word') : $t('engine.add_word')" width="500px">
      <el-form :model="wordForm" label-width="100px">
        <el-form-item :label="$t('engine.word')">
          <el-input v-model="wordForm.word" :disabled="!!editingWord" />
        </el-form-item>
        <el-form-item :label="$t('engine.score')">
          <el-input-number v-model="wordForm.score" :min="-4" :max="4" />
        </el-form-item>
        <el-form-item :label="$t('engine.category')">
          <el-select v-model="wordForm.category">
            <el-option label="negative_strong" value="negative_strong" />
            <el-option label="negative_moderate" value="negative_moderate" />
            <el-option label="negative_mild" value="negative_mild" />
            <el-option label="neutral" value="neutral" />
            <el-option label="positive_mild" value="positive_mild" />
            <el-option label="positive_moderate" value="positive_moderate" />
            <el-option label="positive_strong" value="positive_strong" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('engine.note')">
          <el-input v-model="wordForm.note" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">{{ $t('engine.cancel') }}</el-button>
        <el-button type="primary" @click="saveWord">{{ $t('engine.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from '../locales/index'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const { t } = useI18n()

const stats = ref({})
const lexiconEntries = ref([])
const loading = ref(false)
const searchKeyword = ref('')
const filterCategory = ref('')
const currentPage = ref(1)
const pageSize = ref(50)
const totalEntries = ref(0)

const showAddDialog = ref(false)
const editingWord = ref(null)
const wordForm = ref({
  word: '',
  score: 0,
  category: 'neutral',
  note: '',
})

onMounted(() => {
  loadStats()
  loadLexicon()
})

async function loadStats() {
  try {
    const resp = await api.get('/emotion-engine/stats')
    stats.value = resp
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

async function loadLexicon() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterCategory.value) params.category = filterCategory.value

    const resp = await api.get('/emotion-engine/lexicon', { params })
    lexiconEntries.value = resp.entries || []
    totalEntries.value = resp.total || 0
  } catch (e) {
    ElMessage.error(t('engine.load_error'))
  } finally {
    loading.value = false
  }
}

function editWord(row) {
  editingWord.value = row.word
  wordForm.value = {
    word: row.word,
    score: row.score,
    category: row.category,
    note: row.note || '',
  }
  showAddDialog.value = true
}

async function saveWord() {
  try {
    if (editingWord.value) {
      await api.put(`/emotion-engine/lexicon/${editingWord.value}`, {
        score: wordForm.value.score,
        category: wordForm.value.category,
        note: wordForm.value.note,
      })
      ElMessage.success(t('engine.update_success'))
    } else {
      await api.post('/emotion-engine/lexicon', wordForm.value)
      ElMessage.success(t('engine.add_success'))
    }
    showAddDialog.value = false
    editingWord.value = null
    loadLexicon()
    loadStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('engine.save_error'))
  }
}

async function deleteWord(word) {
  try {
    await ElMessageBox.confirm(
      t('engine.delete_confirm', { word }),
      t('engine.delete_title'),
      { type: 'warning' }
    )
    await api.delete(`/emotion-engine/lexicon/${word}`)
    ElMessage.success(t('engine.delete_success'))
    loadLexicon()
    loadStats()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(t('engine.delete_error'))
    }
  }
}
</script>

<style scoped>
.emotion-engine-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.page-subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #409eff;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #999;
  margin-top: 8px;
}

.section-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.score-positive {
  color: #67c23a;
  font-weight: 600;
}

.score-negative {
  color: #f56c6c;
  font-weight: 600;
}
</style>
