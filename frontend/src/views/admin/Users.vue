<template>
  <div class="admin-users">
    <div class="page-header">
      <h1 class="page-title">用户管理</h1>
      <p class="page-subtitle">管理系统注册用户</p>
    </div>

    <!-- 搜索和筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="8" :md="6">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索昵称..."
            clearable
            @input="onSearch"
            @clear="onSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="6" :md="4">
          <el-select
            v-model="roleFilter"
            placeholder="角色筛选"
            clearable
            @change="onFilterChange"
            style="width: 100%"
          >
            <el-option label="全部角色" value="" />
            <el-option label="站长" value="super_admin" />
            <el-option label="副站长" value="admin" />
            <el-option label="编者" value="editor" />
            <el-option label="读者" value="reader" />
            <el-option label="已封禁" value="banned" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="6" :md="4">
          <el-select
            v-model="tierFilter"
            placeholder="订阅筛选"
            clearable
            @change="onFilterChange"
            style="width: 100%"
          >
            <el-option label="全部订阅" value="" />
            <el-option label="免费版" value="free" />
            <el-option label="专业版" value="pro" />
            <el-option label="高级版" value="premium" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4" :md="2">
          <el-button type="primary" @click="fetchUsers" :loading="loading">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 用户表格 -->
    <el-card class="table-card" shadow="never">
      <el-table
        :data="userList"
        v-loading="loading"
        stripe
        style="width: 100%"
        @row-click="openEditDialog"
        highlight-current-row
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="nickname" label="昵称" min-width="120" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="订阅" width="100">
          <template #default="{ row }">
            <el-tag :type="tierTagType(row.subscription_tier)" size="small">
              {{ tierLabel(row.subscription_tier) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI调用/月" width="110" align="right">
          <template #default="{ row }">
            {{ row.ai_calls_this_month ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="存储用量" width="110" align="right">
          <template #default="{ row }">
            {{ formatBytes(row.storage_used_bytes ?? 0) }}
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click.stop="openEditDialog(row)">编辑</el-button>
            <el-button
              v-if="row.role !== 'banned'"
              text
              type="danger"
              size="small"
              @click.stop="handleBan(row)"
            >封禁</el-button>
            <el-button
              v-else
              text
              type="success"
              size="small"
              @click.stop="handleUnban(row)"
            >解封</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>

    <!-- 编辑用户弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="编辑用户"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="editForm" label-width="100px" label-position="left">
        <el-form-item label="用户ID">
          <el-input :model-value="editForm.id" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="editForm.nickname" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option label="站长" value="super_admin" />
            <el-option label="副站长" value="admin" />
            <el-option label="编者" value="editor" />
            <el-option label="读者" value="reader" />
            <el-option label="已封禁" value="banned" />
          </el-select>
        </el-form-item>
        <el-form-item label="订阅等级">
          <el-select v-model="editForm.subscription_tier" style="width: 100%">
            <el-option label="免费版" value="free" />
            <el-option label="专业版" value="pro" />
            <el-option label="高级版" value="premium" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI调用次数">
          <el-input-number
            v-model="editForm.ai_calls_this_month"
            :min="0"
            :step="1"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api/adminApi'

const loading = ref(false)
const saving = ref(false)
const userList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const roleFilter = ref('')
const tierFilter = ref('')

const dialogVisible = ref(false)
const editForm = ref({})

let searchTimer = null

function roleLabel(role) {
  const map = { super_admin: '站长', admin: '副站长', editor: '编者', reader: '读者', guest: '游客', premium: '付费用户', banned: '已封禁' }
  return map[role] || role || '未知'
}

function roleTagType(role) {
  const map = { super_admin: 'danger', admin: 'danger', editor: 'warning', reader: 'info', guest: 'info', premium: 'success', banned: 'warning' }
  return map[role] || 'info'
}

function tierLabel(tier) {
  const map = { free: '免费版', pro: '专业版', premium: '高级版' }
  return map[tier] || tier || '未知'
}

function tierTagType(tier) {
  const map = { free: 'info', pro: 'warning', premium: 'success' }
  return map[tier] || 'info'
}

function formatDate(dateStr) {
  if (!dateStr) return '--'
  try {
    const d = new Date(dateStr)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return dateStr
  }
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value.trim()) {
      params.nickname = searchKeyword.value.trim()
    }
    if (roleFilter.value) {
      params.role = roleFilter.value
    }
    if (tierFilter.value) {
      params.subscription_tier = tierFilter.value
    }
    const res = await adminApi.getUsers(params)
    userList.value = res.users || res.items || []
    total.value = res.total || 0
  } catch (e) {
    ElMessage.error('获取用户列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    fetchUsers()
  }, 400)
}

function onFilterChange() {
  currentPage.value = 1
  fetchUsers()
}

function openEditDialog(row) {
  editForm.value = { ...row }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    await adminApi.updateUser(editForm.value.id, {
      nickname: editForm.value.nickname,
      role: editForm.value.role,
      subscription_tier: editForm.value.subscription_tier,
      ai_calls_this_month: editForm.value.ai_calls_this_month,
    })
    ElMessage.success('用户信息已更新')
    dialogVisible.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleBan(row) {
  try {
    await ElMessageBox.confirm(
      `确定要封禁用户「${row.nickname}」吗？封禁后该用户将无法登录。`,
      '确认封禁',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await adminApi.updateUser(row.id, { role: 'banned' })
    ElMessage.success('用户已封禁')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
  }
}

async function handleUnban(row) {
  try {
    await ElMessageBox.confirm(
      `确定要解除「${row.nickname}」的封禁吗？`,
      '确认解封',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
    await adminApi.updateUser(row.id, { role: 'reader' })
    ElMessage.success('用户已解封，恢复为读者')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.admin-users {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-2xl);
}

.page-header {
  margin-bottom: var(--space-2xl);
}

.page-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: var(--text-h2);
  font-weight: 500;
  color: var(--near-black);
  letter-spacing: 0.06em;
  margin: 0 0 var(--space-sm) 0;
}

.page-subtitle {
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  color: var(--stone-gray);
  margin: 0;
}

.filter-card {
  margin-bottom: var(--space-lg);
}

.table-card {
  margin-bottom: var(--space-lg);
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: var(--space-xl);
}
</style>
