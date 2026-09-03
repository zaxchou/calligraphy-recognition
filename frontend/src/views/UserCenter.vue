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
              <span>{{ $t('usercenter.t1') }}</span>
            </div>
          </div>
          <input ref="avatarInputRef" type="file" accept="image/*" style="display:none" @change="handleAvatarFile" />
          <p v-if="avatarUploading" class="uc-avatar-status">{{ $t('usercenter.t2') }}</p>
          <AvatarCropper ref="cropperRef" @cropped="onAvatarCropped" />
        </div>

        <!-- 基本信息（只读） -->
        <div class="uc-info-block">
          <h3 class="uc-block-title">{{ $t('usercenter.t3') }}</h3>
          <div class="uc-info-rows">
            <div class="uc-info-row">
              <span class="uc-info-label">UID</span>
              <span class="uc-info-value" style="font-weight:600;color:#c8a45c;">{{ profile?.uid || authStore.userInfo?.uid || '-' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('usercenter.t4') }}</span>
              <span class="uc-info-value">{{ profile?.phone || '未绑定' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('usercenter.t5') }}</span>
              <span class="uc-info-value">{{ profile?.email || '未绑定' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('librarydetail.a17') }}</span>
              <span class="uc-info-value">
                <span class="uc-role-tag" :class="'role-' + (authStore.role || 'guest')">{{ roleLabel(authStore.role) }}</span>
              </span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('usercenter.t6') }}</span>
              <span class="uc-info-value">
                <span style="font-weight:600;color:#c8a45c;">{{ authStore.score }}</span>
                <span style="font-size:12px;color:#999;margin-left:4px;">{{ $t('usercenter.t7') }}</span>
              </span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('usercenter.t8') }}</span>
              <span class="uc-info-value">{{ profile?.created_at ? formatDate(profile.created_at) : '-' }}</span>
            </div>
            <div class="uc-info-row">
              <span class="uc-info-label">{{ $t('usercenter.t9') }}</span>
              <span class="uc-info-value">
                <template v-if="profile?.claimed_artists?.length">
                  <span class="uc-artist-tag" v-for="a in profile.claimed_artists" :key="a">{{ a }}</span>
                </template>
                <span v-else class="uc-muted">{{ $t('usercenter.t10') }}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：可编辑资料 -->
      <div class="uc-right">
        <!-- 编辑资料 -->
        <div class="uc-card">
          <h3 class="uc-block-title">{{ $t('usercenter.t11') }}</h3>
          <div class="uc-form">
            <div class="uc-field">
              <label class="uc-field-label">{{ $t('librarydetail.a16') }}<span class="uc-field-hint">{{ $t('usercenter.t12') }}</span></label>
              <input class="uc-input" v-model="editForm.nickname" :placeholder="$t('usercenter.a1')" maxlength="20" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">{{ $t('usercenter.t5') }}</label>
              <input class="uc-input" v-model="editForm.email" :placeholder="$t('usercenter.a2')" type="email" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">{{ $t('usercenter.t4') }}</label>
              <input class="uc-input" v-model="editForm.phone" :placeholder="$t('login.s1')" maxlength="11" />
            </div>
            <button class="uc-btn primary" :disabled="profileSaving" @click="handleUpdateProfile">
              {{ profileSaving ? '保存中...' : '保存资料' }}
            </button>
          </div>
        </div>

        <!-- 修改密码 -->
        <div class="uc-card">
          <h3 class="uc-block-title">{{ $t('usercenter.t13') }}</h3>
          <div class="uc-form">
            <div v-if="profile?.has_password" class="uc-field">
              <label class="uc-field-label">{{ $t('usercenter.t14') }}</label>
              <input class="uc-input" v-model="pwdForm.old_password" type="password" :placeholder="$t('usercenter.s9')" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">{{ $t('usercenter.t15') }}</label>
              <input class="uc-input" v-model="pwdForm.password" type="password" :placeholder="$t('usercenter.a3')" maxlength="32" />
            </div>
            <div class="uc-field">
              <label class="uc-field-label">{{ $t('usercenter.t16') }}</label>
              <input class="uc-input" v-model="pwdForm.confirm" type="password" :placeholder="$t('usercenter.a4')" />
            </div>
            <button class="uc-btn primary" :disabled="pwdSaving" @click="handleChangePassword">
              {{ pwdSaving ? '修改中...' : '修改密码' }}
            </button>
          </div>
        </div>

        <!-- 我的贡献 -->
        <div class="uc-card">
          <h3 class="uc-block-title">{{ $t('usercenter.t17') }}</h3>
          <div v-if="contributionsLoading" style="text-align:center;padding:20px;">
            <el-icon class="is-loading" size="20"><Loading /></el-icon>
          </div>
          <div v-else-if="contributions.length === 0" style="padding:12px 0;color:#999;font-size:13px;">
            {{ $t('usercenter.t18') }}
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
import { translate as t } from '@/locales'

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
    ElMessage.error(t('usercenter.s1'))
  }
}

function triggerAvatarUpload() {
  avatarInputRef.value?.click()
}

function handleAvatarFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) { ElMessage.warning(t('usercenter.s2')); return }
  if (!cropperRef.value) { ElMessage.error(t('usercenter.s3')); return }
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
      ElMessage.success(t('usercenter.s4'))
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '头像上传失败')
    avatarPreview.value = authStore.avatarUrl || ''
  } finally {
    avatarUploading.value = false
  }
}

async function handleUpdateProfile() {
  if (!editForm.nickname.trim()) { ElMessage.warning(t('usercenter.s5')); return }
  profileSaving.value = true
  try {
    await api.put('/auth/profile', {
      nickname: editForm.nickname.trim(),
      email: editForm.email.trim() || null,
      phone: editForm.phone.trim() || null,
    })
    await authStore.refreshProfile()
    ElMessage.success(t('usercenter.s6'))
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
  if (!pwdForm.password || pwdForm.password.length < 6) { ElMessage.warning(t('usercenter.s7')); return }
  if (pwdForm.password !== pwdForm.confirm) { ElMessage.warning(t('usercenter.s8')); return }
  pwdSaving.value = true
  try {
    const payload = { password: pwdForm.password }
    if (profile.value?.has_password) {
      if (!pwdForm.old_password) { ElMessage.warning(t('usercenter.s9')); pwdSaving.value = false; return }
      payload.old_password = pwdForm.old_password
    }
    await api.put('/auth/password', payload)
    ElMessage.success(t('usercenter.s10'))
    pwdForm.old_password = ''
    pwdForm.password = ''
    pwdForm.confirm = ''
    await loadProfile()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '修改失败')
  } finally { pwdSaving.value = false }
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
