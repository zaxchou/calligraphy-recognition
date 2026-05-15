<template>
  <div class="ss-page">
    <div class="ss-header">
      <h2 class="ss-title">系统设置</h2>
      <p class="ss-desc">修改后即时生效，无需重新部署。游客看到的标题、副标题、页脚等都会同步更新。</p>
    </div>

    <div class="ss-card" v-loading="loading">
      <!-- 错误提示 -->
      <div v-if="loadError" class="ss-alert ss-alert-error">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ loadError }}</span>
        <button class="ss-alert-retry" @click="load">重试</button>
      </div>

      <!-- 分组：品牌信息 -->
      <div class="ss-section">
        <h3 class="ss-section-title">品牌信息</h3>
        <div class="ss-grid">
          <div class="ss-field" v-for="item in brandFields" :key="item.key">
            <label class="ss-label">{{ item.label }}</label>
            <input
              class="ss-input"
              v-model="form[item.key]"
              :placeholder="item.placeholder"
              @input="onFieldChange"
            />
            <span class="ss-hint">{{ item.hint }}</span>
          </div>
        </div>
      </div>

      <!-- 分组：页脚与署名 -->
      <div class="ss-section">
        <h3 class="ss-section-title">页脚与署名</h3>
        <div class="ss-grid">
          <div class="ss-field" v-for="item in footerFields" :key="item.key">
            <label class="ss-label">{{ item.label }}</label>
            <input
              class="ss-input"
              v-model="form[item.key]"
              :placeholder="item.placeholder"
              @input="onFieldChange"
            />
            <span class="ss-hint">{{ item.hint }}</span>
          </div>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="ss-actions">
        <button class="ss-btn-save" :disabled="saving || !dirty" @click="save">
          <el-icon v-if="saving" class="is-loading"><Loading /></el-icon>
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
        <button class="ss-btn-reset" :disabled="saving || !dirty" @click="reset">
          取消
        </button>
        <span v-if="msg" class="ss-msg" :class="{ error: msgErr }">{{ msg }}</span>
      </div>
    </div>

    <!-- 预览卡片 -->
    <div class="ss-preview" v-if="!loading && !loadError">
      <h3 class="ss-preview-title">预览效果</h3>
      <div class="ss-preview-card">
        <div class="preview-logo">
          <span class="preview-title">{{ form.title || '墨林百科' }}</span>
          <span class="preview-subtitle">{{ form.subtitle || '最智能的中国画与书法大库' }}</span>
        </div>
        <div class="preview-browser">
          <span class="preview-tab">{{ form.full_title || '墨林百科 - 最智能的中国画与书法大库' }}</span>
        </div>
        <div class="preview-footer">
          {{ form.footer || '墨林百科 © 2026' }}
          <span v-if="form.author"> · {{ form.author }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { WarningFilled, Loading } from '@element-plus/icons-vue'

const loading = ref(true)
const saving = ref(false)
const msg = ref('')
const msgErr = ref(false)
const loadError = ref('')
const dirty = ref(false)
const initialForm = {}

const brandFields = [
  { key: 'title',      label: '网站标题',      placeholder: '墨林百科',       hint: '导航栏 logo、登录页标题' },
  { key: 'subtitle',   label: '副标题',        placeholder: '最智能的中国画与书法大库', hint: 'logo 下方、首页 hero 区' },
  { key: 'full_title', label: '全称',          placeholder: '墨林百科 - 最智能的中国画与书法大库', hint: '浏览器标签页标题' },
  { key: 'domain',     label: '域名',          placeholder: 'molin.wiki',    hint: '当前域名' },
]

const footerFields = [
  { key: 'footer',     label: '页脚文案',      placeholder: '墨林百科 © 2026', hint: '页面底部' },
  { key: 'author',     label: '作者署名',      placeholder: '周豪 Zax',       hint: '页脚署名' },
]

const form = reactive({
  title: '', subtitle: '', full_title: '', domain: '', footer: '', author: '',
})

function onFieldChange() {
  dirty.value = true
}

onMounted(async () => {
  await load()
})

async function load() {
  loading.value = true
  loadError.value = ''
  msg.value = ''
  try {
    const token = localStorage.getItem('auth_token')
    const resp = await fetch('/api/v1/admin/site-settings', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (resp.ok) {
      const data = await resp.json()
      const s = data.settings || {}
      for (const f of [...brandFields, ...footerFields]) {
        if (s[f.key] !== undefined) {
          form[f.key] = s[f.key]
          initialForm[f.key] = s[f.key]
        }
      }
    } else {
      // 尝试解析错误消息，失败则用状态码
      let errMsg = `HTTP ${resp.status}`
      try {
        const err = await resp.json()
        errMsg = err.detail || errMsg
      } catch {}
      if (resp.status === 401 || resp.status === 403) {
        loadError.value = '您没有管理员权限，无法加载系统设置。请确认已登录管理员账号。'
      } else {
        loadError.value = `加载失败：${errMsg}`
      }
    }
  } catch (e) {
    loadError.value = '网络请求失败：' + e.message
  } finally {
    loading.value = false
  }
}

function reset() {
  for (const f of [...brandFields, ...footerFields]) {
    form[f.key] = initialForm[f.key] || ''
  }
  dirty.value = false
  msg.value = ''
}

async function save() {
  saving.value = true
  msg.value = ''
  try {
    // 只发送有值的字段 + 已修改的字段（防止空值覆盖现有数据）
    const payload = {}
    for (const f of [...brandFields, ...footerFields]) {
      const val = form[f.key]?.trim()
      if (val) {
        payload[f.key] = val
      }
    }

    const token = localStorage.getItem('auth_token')
    const resp = await fetch('/api/v1/admin/site-settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ settings: payload }),
    })

    if (resp.ok) {
      // 更新 initialForm 以匹配已保存的值
      for (const f of [...brandFields, ...footerFields]) {
        initialForm[f.key] = form[f.key]
      }
      // 写入 localStorage 作为前端缓存
      localStorage.setItem('molin_site_config', JSON.stringify({ ...form }))
      dirty.value = false
      msg.value = '设置已保存，刷新页面即可看到效果'
      msgErr.value = false
    } else {
      let errMsg = `HTTP ${resp.status}`
      try {
        const err = await resp.json()
        errMsg = err.detail || errMsg
      } catch {
        // 响应不是 JSON（如 500 纯文本错误）
        const text = await resp.text()
        errMsg = text.substring(0, 80) || errMsg
      }
      msg.value = errMsg
      msgErr.value = true
    }
  } catch (e) {
    msg.value = '请求失败: ' + e.message
    msgErr.value = true
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.ss-page {
  padding: 24px 32px;
  max-width: 780px;
}

/* 头部 */
.ss-header {
  margin-bottom: 24px;
}
.ss-title {
  font-size: 22px;
  font-weight: 700;
  color: #3a3222;
  margin: 0 0 6px;
  font-family: 'Noto Serif SC', serif;
}
.ss-desc {
  font-size: 13px;
  color: #8c7a5c;
  margin: 0;
  line-height: 1.6;
}

/* 卡片容器 */
.ss-card {
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

/* 错误提示 */
.ss-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 20px;
}
.ss-alert-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}
.ss-alert-retry {
  margin-left: auto;
  padding: 4px 12px;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  background: #fff;
  color: #b91c1c;
  font-size: 12px;
  cursor: pointer;
}
.ss-alert-retry:hover {
  background: #fef2f2;
}

/* 分组 */
.ss-section {
  margin-bottom: 24px;
}
.ss-section:last-of-type {
  margin-bottom: 0;
}
.ss-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #5c5346;
  margin: 0 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0ebe0;
}

/* 字段网格 */
.ss-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.ss-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ss-label {
  font-size: 13px;
  font-weight: 500;
  color: #5c5346;
}
.ss-input {
  width: 100%;
  padding: 9px 12px;
  font-size: 14px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  background: #faf9f5;
  color: #2c2416;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ss-input:focus {
  border-color: #c8a45c;
  box-shadow: 0 0 0 3px rgba(200,164,92,0.12);
  background: #fff;
}
.ss-hint {
  font-size: 11px;
  color: #b0a890;
}

/* 操作栏 */
.ss-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f0ebe0;
}
.ss-btn-save {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  background: #c45a3c;
  color: #fff;
  transition: opacity 0.2s;
}
.ss-btn-save:hover:not(:disabled) { opacity: 0.9; }
.ss-btn-save:disabled { opacity: 0.45; cursor: not-allowed; }

.ss-btn-reset {
  padding: 9px 16px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #8c7a5c;
  cursor: pointer;
  transition: all 0.2s;
}
.ss-btn-reset:hover:not(:disabled) {
  border-color: #c45a3c;
  color: #c45a3c;
}
.ss-btn-reset:disabled { opacity: 0.4; cursor: not-allowed; }

.ss-msg {
  font-size: 13px;
  margin-left: 4px;
}
.ss-msg:not(.error) { color: #5a8a4a; }
.ss-msg.error { color: #d03030; }

/* 预览卡片 */
.ss-preview {
  margin-top: 0;
}
.ss-preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #8c7a5c;
  margin: 0 0 10px;
}
.ss-preview-card {
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 12px;
  overflow: hidden;
}

.preview-logo {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid #f0ebe0;
}
.preview-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 18px;
  font-weight: 700;
  color: #c45a3c;
}
.preview-subtitle {
  font-size: 12px;
  color: #8c7a5c;
}

.preview-browser {
  padding: 8px 24px;
  background: #faf9f5;
  border-bottom: 1px solid #f0ebe0;
}
.preview-tab {
  font-size: 11px;
  color: #b0a890;
}

.preview-footer {
  padding: 14px 24px;
  font-size: 12px;
  color: #b0a890;
  text-align: center;
}
</style>
