<template>
  <div class="uc-page">
    <div class="uc-layout">
      <!-- 左侧：头像 + 基本信息 -->
      <div class="uc-left">
        <!-- 头像 -->
        <div class="uc-avatar-section">
          <div class="uc-avatar-wrap" @click="triggerAvatarUpload">
            <img v-if="avatarPreview" :src="avatarPreview" class="uc-avatar-img" />
            <span v-else class="uc-avatar-placeholder">{{ authStore.nickname?.charAt(0) || '用' }}</span>
            <div class="uc-avatar-overlay">
              <span>更换</span>
            </div>
          </div>
          <input ref="avatarInputRef" type="file" accept="image/*" style="display:none" @change="handleAvatarFile" />
          <p v-if="avatarUploading" class="uc-avatar-status">上传中...</p>
          <AvatarCropper ref="cropperRef" @cropped="onAvatarCropped" />
        </div>

        <!-- 基本信息（只读） -->
        <div class="uc-info-block">
          <h3 class="uc-block-title">基本信息</h3>
          <div class="uc-info-rows">
            <div class="uc-info-row">
              <span class="uc-info-label">UID</span>
              <span class="uc-info-value" style="font-weight:600;color:#c8a45c;">{{ profile?.uid || authStore.userInfo?.uid || '-' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">手机号</span>
              <span class="uc-info-value">{{ profile?.phone || '未绑定' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">邮箱</span>
              <span class="uc-info-value">{{ profile?.email || '未绑定' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">角色</span>
              <span class="uc-info-value">
                <span class="uc-role-tag" :class="'role-' + (authStore.role || 'guest')">{{ roleLabel(authStore.role) }}</span>
              </span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">贡献积分</span>
              <span class="uc-info-value">
                <span style="font-weight:600;color:#c8a45c;">{{ authStore.score }}</span>
                <span style="font-size:12px;color:#999;margin-left:4px;">分</span>
              </span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">注册时间</span>
              <span class="uc-info-value">{{ profile?.created_at ? formatDate(profile.created_at) : '-' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">已认领画家</span>
              <span class="uc-info-value">
                <template v-if="profile?.claimed_artists?.length">
                  <span class="uc-artist-tag" v-for="a in profile.claimed_artists" :key="a">{{ a }}</span>
                </template>
                <span v-else class="uc-muted">暂无</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：可编辑资料 -->
      <div class="uc-right">
        <!-- 编辑资料 -->
        <div class="uc-card">
          <h3 class="uc-block-title">编辑资料</h3>
          <div class="uc-form">
            <div class="uc-field">
              <label class="uc-field-label">昵称 <span class="uc-field-hint">（每年限修改一次，全站唯一）</span></label>
              <input class="uc-input" v-model="editForm.nickname" placeholder="请输入昵称" maxlength="20" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">邮箱</label>
              <input class="uc-input" v-model="editForm.email" placeholder="请输入邮箱" type="email" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">手机号</label>
              <input class="uc-input" v-model="editForm.phone" placeholder="请输入手机号" maxlength="11" />
            </div>
            <button class="uc-btn primary" :disabled="profileSaving" @click="handleUpdateProfile">
              {{ profileSaving ? '保存中...' : '保存资料' }}
            </button>
          </div>
        </div>

        <!-- 修改密码 -->
        <div class="uc-card">
          <h3 class="uc-block-title">修改密码</h3>
          <div class="uc-form">
            <div v-if="profile?.has_password" class="uc-field">
              <label class="uc-field-label">旧密码</label>
              <input class="uc-input" v-model="pwdForm.old_password" type="password" placeholder="请输入旧密码" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">新密码</label>
              <input class="uc-input" v-model="pwdForm.password" type="password" placeholder="至少6位" maxlength="32" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">确认新密码</label>
              <input class="uc-input" v-model="pwdForm.confirm" type="password" placeholder="再次输入新密码" />
            </div>
            <button class="uc-btn primary" :disabled="pwdSaving" @click="handleChangePassword">
              {{ pwdSaving ? '修改中...' : '修改密码' }}
            </button>
          </div>
        </div>

        <!-- 微信绑定 -->
        <div class="uc-card">
          <h3 class="uc-block-title">账号绑定</h3>
          <div class="uc-bind-row">
            <span class="uc-bind-label">微信</span>
            <span v-if="profile?.has_wechat" class="uc-bind-status bound">已绑定</span>
            <span v-else class="uc-bind-status">未绑定</span>
            <button
              v-if="!profile?.has_wechat"
              class="uc-btn small"
              style="background:#07c160;color:#fff;"
              @click="handleBindWechat"
            >绑定微信</button>
          </div>
        </div>

        <!-- 我的贡献 -->
        <div class="uc-card">
          <h3 class="uc-block-title">我的贡献</h3>
          <div v-if="contributionsLoading" style="text-align:center;padding:20px;">
            <el-icon class="is-loading" size="20"><Loading /></el-icon>
          </div>
          <div v-else-if="contributions.length === 0" style="padding:12px 0;color:#999;font-size:13px;">
            你还没有提交过修改建议。
          </div>
          <el-timeline v-else>
            <el-timeline-item
              v-for="c in contributions" :key="c.id"
              :timestamp="c.created_at"
              placement="top"
              size="small"
            >
              <div style="font-size:13px;">
                <strong>{{ c.artwork_title || '作品' }}</strong>
                <span style="color:#999;margin:0 4px;">→</span>
                <span>{{ c.field_name || c.request_type }}</span>
                <el-tag
                  :type="c.status === 'approved' ? 'success' : c.status === 'rejected' ? 'danger' : 'warning'"
                  size="small" style="margin-left:8px;"
                >
                  {{ c.status === 'approved' ? '已通过' : c.status === 'rejected' ? '已驳回' : '待审核' }}
                </el-tag>
                <p v-if="c.change_summary" style="margin:4px 0 0;color:#888;font-size:12px;">
                  {{ c.change_summary }}
                </p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import api, { notificationApi } from '../api'
import AvatarCropper from '../components/AvatarCropper.vue'

const authStore = useAuthStore()
const router = useRouter()

const profile = ref(null)
const profileSaving = ref(false)
const pwdSaving = ref(false)
const avatarPreview = ref(authStore.avatarUrl || '')
const avatarUploading = ref(false)
const avatarInputRef = ref(null)
const cropperRef = ref(null)

const editForm = reactive({ nickname: '', email: '', phone: '' })
const pwdForm = reactive({ old_password: '', password: '', confirm: '' })
const contributions = ref([])
const contributionsLoading = ref(false)

const roleLabels = {
  super_admin: '站长', admin: '副站长', editor: '编者',
  reader: '读者', guest: '游客', premium: '付费用户', banned: '封禁',
}
function roleLabel(r) { return roleLabels[r] || r || '未知' }
function formatDate(s) { return s ? new Date(s).toLocaleDateString('zh-CN') : '-' }

onMounted(async () => {
  if (!authStore.isLoggedIn) {
    router.push({ name: 'Login', query: { redirect: '/user/center' } })
    return
  }
  await loadProfile()
  await loadContributions()
})

async function loadProfile() {
  try {
    const resp = await api.get('/auth/profile')
    profile.value = resp
    editForm.nickname = resp.nickname || ''
    editForm.email = resp.email || ''
    editForm.phone = resp.phone || ''
    avatarPreview.value = authStore.avatarUrl || resp.avatar_url || ''
  } catch (e) {
    ElMessage.error('加载用户信息失败')
  }
}

function triggerAvatarUpload() {
  avatarInputRef.value?.click()
}

function handleAvatarFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) { ElMessage.warning('头像文件不能超过10MB'); return }
  if (!cropperRef.value) { ElMessage.error('裁剪组件未加载，请刷新页面重试'); return }
  cropperRef.value.open(file)
  // 延迟清除避免触发二次 change 事件
  setTimeout(() => { e.target.value = '' }, 100)
}

async function onAvatarCropped(blob) {
  avatarUploading.value = true
  try {
    // 本地预览
    avatarPreview.value = URL.createObjectURL(blob)

    const formData = new FormData()
    formData.append('file', blob, 'avatar.jpg')
    const resp = await api.post('/auth/avatar', formData)
    if (resp.avatar_url) {
      avatarPreview.value = resp.avatar_url
      await authStore.refreshProfile()
      ElMessage.success('头像已更新')
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '头像上传失败')
    avatarPreview.value = authStore.avatarUrl || ''
  } finally {
    avatarUploading.value = false
  }
}

async function handleUpdateProfile() {
  if (!editForm.nickname.trim()) { ElMessage.warning('昵称不能为空'); return }
  profileSaving.value = true
  try {
    await api.put('/auth/profile', {
      nickname: editForm.nickname.trim(),
      email: editForm.email.trim() || null,
      phone: editForm.phone.trim() || null,
    })
    await authStore.refreshProfile()
    ElMessage.success('资料已更新')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally { profileSaving.value = false }
}

async function loadContributions() {
  contributionsLoading.value = true
  try {
    const resp = await notificationApi.myContributions()
    contributions.value = resp.contributions || []
  } catch (e) {
    console.error('加载贡献记录失败', e)
  } finally {
    contributionsLoading.value = false
  }
}

async function handleChangePassword() {
  if (!pwdForm.password || pwdForm.password.length < 6) { ElMessage.warning('新密码至少6位'); return }
  if (pwdForm.password !== pwdForm.confirm) { ElMessage.warning('两次输入的新密码不一致'); return }
  pwdSaving.value = true
  try {
    const payload = { password: pwdForm.password }
    if (profile.value?.has_password) {
      if (!pwdForm.old_password) { ElMessage.warning('请输入旧密码'); pwdSaving.value = false; return }
      payload.old_password = pwdForm.old_password
    }
    await api.put('/auth/password', payload)
    ElMessage.success('密码修改成功')
    pwdForm.old_password = ''
    pwdForm.password = ''
    pwdForm.confirm = ''
    await loadProfile()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '修改失败')
  } finally { pwdSaving.value = false }
}

function handleBindWechat() {
  const base = import.meta.env.VITE_API_BASE || ''
  window.location.href = `${base}/api/v1/auth/wechat/qrcode?action=bind&redirect=${encodeURIComponent('/user/center')}`
}
</script>

<style scoped>
.uc-page { padding: 2rem; min-height: 70vh; }

.uc-layout {
  max-width: 860px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  align-items: start;
}

/* ===== 左侧 ===== */
.uc-left {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.uc-avatar-section {
  text-align: center;
}

.uc-avatar-wrap {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  margin: 0 auto;
  position: relative;
  cursor: pointer;
  overflow: hidden;
  border: 2px solid #e8e4d8;
  background: #f5f0e8;
}

.uc-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.uc-avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  color: #c8a45c;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

.uc-avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.uc-avatar-overlay span {
  color: #fff;
  font-size: 13px;
}

.uc-avatar-wrap:hover .uc-avatar-overlay { opacity: 1; }

.uc-avatar-status { font-size: 12px; color: #c8a45c; margin-top: 8px; }

/* 信息块 */
.uc-info-block {
  background: #faf9f5;
  border: 1px solid #e8e4d8;
  border-radius: 10px;
  padding: 20px;
}

.uc-info-block .uc-block-title {
  font-size: 14px;
  font-weight: 600;
  color: #3a3222;
  margin: 0 0 14px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #e8e4d8;
}

.uc-info-rows { display: flex; flex-direction: column; gap: 12px; }

.uc-info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.uc-info-label { font-size: 12px; color: #999; white-space: nowrap; }
.uc-info-value { font-size: 13px; color: #2c2416; text-align: right; }

.uc-role-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 3px;
  background: #f0ebe0;
  color: #8c7a5c;
}
.uc-role-tag.role-super_admin { background: #c45a3c20; color: #c45a3c; }
.uc-role-tag.role-admin { background: #c8a45c20; color: #9a7a3c; }
.uc-role-tag.role-editor { background: #3a8c5c20; color: #3a8c5c; }

.uc-artist-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  margin: 0 2px 3px 0;
  background: #f5efe0;
  border-radius: 3px;
  color: #8c7a5c;
}

.uc-muted { color: #ccc; }

/* ===== 右侧 ===== */
.uc-right { display: flex; flex-direction: column; gap: 16px; }

.uc-card {
  background: #faf9f5;
  border: 1px solid #e8e4d8;
  border-radius: 10px;
  padding: 24px;
}

.uc-block-title {
  font-size: 14px;
  font-weight: 600;
  color: #3a3222;
  margin: 0 0 16px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #e8e4d8;
}

.uc-form { display: flex; flex-direction: column; gap: 14px; }

.uc-field { display: flex; flex-direction: column; gap: 5px; }
.uc-field-label { font-size: 13px; color: #5c5346; font-weight: 500; }
.uc-field-hint { font-size: 11px; color: #b0a890; font-weight: 400; }

.uc-input {
  width: 100%;
  padding: 9px 12px;
  font-size: 14px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  background: #fff;
  color: #2c2416;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
  line-height: 1.5;
}
.uc-input:focus { border-color: #c8a45c; box-shadow: 0 0 0 2px rgba(200,164,92,0.15); }
.uc-input::placeholder { color: #b0a890; }

.uc-btn {
  padding: 9px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
  align-self: flex-start;
}
.uc-btn.primary { background: #c45a3c; color: #fff; }
.uc-btn.primary:hover { opacity: 0.9; }
.uc-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.uc-btn.small { padding: 5px 14px; font-size: 12px; }

/* 绑定行 */
.uc-bind-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}
.uc-bind-label { font-size: 14px; color: #3a3222; min-width: 40px; }
.uc-bind-status { font-size: 13px; color: #999; }
.uc-bind-status.bound { color: #07c160; }

/* 响应式 */
@media (max-width: 640px) {
  .uc-layout {
    grid-template-columns: 1fr;
  }
}
</style>
