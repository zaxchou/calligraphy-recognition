<template>
  <div class="admin-permissions">
    <div class="page-header">
      <h1 class="page-title">权限配置</h1>
      <p class="page-subtitle">为每个角色配置可访问的管理功能</p>
    </div>

    <el-card class="perm-card" shadow="never" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-header-title">角色权限矩阵</span>
          <el-button type="primary" size="small" :loading="saving" @click="handleSave">保存配置</el-button>
        </div>
      </template>

      <div class="perm-note">
        <el-icon><InfoFilled /></el-icon>
        <span>站长（super_admin）始终拥有全部权限，无需配置</span>
      </div>

      <div class="perm-table-wrap" v-if="permissions">
        <table class="perm-table">
          <thead>
            <tr>
              <th class="perm-label-col">权限</th>
              <th class="perm-role-col" v-for="role in roles" :key="role.key">
                <span class="role-name">{{ role.label }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groups" :key="group.category">
              <tr class="group-header">
                <td colspan="4">
                  <span class="group-name">{{ group.category }}</span>
                </td>
              </tr>
              <tr v-for="pk in group.perms" :key="pk.key">
                <td class="perm-label-col">
                  <span class="perm-label">{{ pk.label }}</span>
                  <span class="perm-key">{{ pk.key }}</span>
                </td>
                <td class="perm-role-col" v-for="role in roles" :key="role.key">
                  <el-checkbox
                    :model-value="hasPerm(role.key, pk.key)"
                    @change="(val) => togglePerm(role.key, pk.key, val)"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div v-else-if="!loading" class="empty-state">加载失败，请刷新重试</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { adminApi } from '../../api/adminApi'

const loading = ref(false)
const saving = ref(false)
const permissions = ref(null)
const allKeys = ref([])

const roles = [
  { key: 'admin', label: '副站长' },
  { key: 'editor', label: '编者' },
  { key: 'reader', label: '读者' },
]

const groups = [
  {
    category: '内容管理',
    perms: [
      { key: 'content.verify', label: '题跋校对' },
      { key: 'content.annotate', label: '标注图校对' },
      { key: 'content.upload', label: '作品上传' },
      { key: 'content.batch', label: '批量操作' },
    ],
  },
  {
    category: '元数据管理',
    perms: [
      { key: 'metadata.dimensions', label: '尺寸录入' },
      { key: 'metadata.seals', label: '印章管理' },
      { key: 'metadata.albums', label: '册页管理' },
      { key: 'metadata.strips', label: '条屏管理' },
      { key: 'metadata.tags', label: '标签管理' },
    ],
  },
  {
    category: '知识管理',
    perms: [
      { key: 'knowledge.artist_info', label: '作者信息' },
      { key: 'knowledge.artist_rules', label: '画家规则' },
    ],
  },
  {
    category: '工具',
    perms: [{ key: 'tools.dedup', label: '作品查重' }],
  },
  {
    category: '系统管理',
    perms: [
      { key: 'system.dashboard', label: '系统概览' },
      { key: 'system.users', label: '用户管理' },
      { key: 'system.permissions', label: '权限配置' },
      { key: 'system.config', label: '系统配置' },
    ],
  },
]

function hasPerm(role, pk) {
  return (permissions.value?.[role] || []).includes(pk)
}

function togglePerm(role, pk, checked) {
  if (!permissions.value[role]) permissions.value[role] = []
  if (checked) {
    if (!permissions.value[role].includes(pk)) {
      permissions.value[role].push(pk)
    }
  } else {
    permissions.value[role] = permissions.value[role].filter(p => p !== pk)
  }
}

async function loadPermissions() {
  loading.value = true
  try {
    const resp = await adminApi.getPermissions()
    permissions.value = resp.permissions || {}
    allKeys.value = resp.all_keys || []
  } catch (e) {
    console.error('获取权限配置失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await adminApi.savePermissions({ permissions: permissions.value })
    ElMessage.success('权限配置已保存')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadPermissions()
})
</script>

<style scoped>
.admin-permissions {
  padding: 24px 32px;
  max-width: 960px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 22px;
  font-weight: 500;
  color: #1c1c1c;
  margin: 0 0 6px 0;
}

.page-subtitle {
  font-size: 13px;
  color: #8c8c8c;
  margin: 0;
}

.perm-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header-title {
  font-size: 14px;
  font-weight: 600;
  color: #3a3222;
}

.perm-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fdf8f0;
  border-radius: 6px;
  font-size: 12px;
  color: #8c7a5c;
  margin-bottom: 16px;
}

.perm-table-wrap {
  overflow-x: auto;
}

.perm-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.perm-table th,
.perm-table td {
  padding: 10px 14px;
  text-align: center;
  border-bottom: 1px solid #f0ede6;
}

.perm-table .perm-label-col {
  text-align: left;
  width: 280px;
}

.perm-table .perm-role-col {
  width: 100px;
}

.perm-table thead th {
  background: #faf9f5;
  font-weight: 600;
  color: #3a3222;
  position: sticky;
  top: 0;
}

.role-name {
  font-size: 13px;
  color: #5c5346;
}

.group-header td {
  background: #f5f0e8;
  padding: 8px 14px;
}

.group-name {
  font-size: 12px;
  font-weight: 600;
  color: #8c7a5c;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.perm-label {
  display: block;
  color: #2c2416;
}

.perm-key {
  display: block;
  font-size: 10px;
  color: #b0a890;
  font-family: monospace;
  margin-top: 2px;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: #8c8c8c;
  font-size: 13px;
}
</style>
