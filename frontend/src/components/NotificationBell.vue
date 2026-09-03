<template>
  <el-dropdown
    trigger="click"
    placement="bottom-end"
    @visible-change="onDropdownVisibleChange"
  >
    <div class="notification-trigger-wrap">
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notification-badge">
        <el-icon :size="20" class="bell-icon">
          <Bell />
        </el-icon>
      </el-badge>
      <span class="t-badge" :data-open="unreadCount > 0 ? 'true' : 'false'">
        <span class="t-badge-dot"></span>
      </span>
    </div>
    <template #dropdown>
      <div class="notification-dropdown" @click.stop>
        <div class="notification-header">
          <span class="notification-title">{{ $t('c-notificationbell.t1') }}</span>
          <el-button
            v-if="notifications.length > 0"
            text
            type="primary"
            size="small"
            @click="handleMarkAllRead"
          >
            {{ $t('c-notificationbell.t2') }}
          </el-button>
        </div>
        <div v-if="loading" class="notification-loading">{{ $t('common.loading') }}</div>
        <div v-else-if="notifications.length === 0" class="notification-empty">
          {{ $t('c-notificationbell.t3') }}
        </div>
        <div v-else class="notification-list">
          <div
            v-for="item in notifications"
            :key="item.id"
            class="notification-item"
            :class="{ unread: !item.is_read }"
            @click="handleClickItem(item)"
          >
            <div class="notification-item-header">
              <span class="notification-item-title">{{ item.title }}</span>
              <el-tag
                :type="tagType(item.type)"
                size="small"
                effect="plain"
              >
                {{ tagLabel(item.type) }}
              </el-tag>
            </div>
            <div v-if="item.body" class="notification-item-body">{{ item.body }}</div>
            <div class="notification-item-time">{{ formatTime(item.created_at) }}</div>
          </div>
        </div>
      </div>
    </template>
  </el-dropdown>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { notificationApi } from '../api'
import { translate as t } from '@/locales'

const router = useRouter()
const unreadCount = ref(0)
const notifications = ref([])
const loading = ref(false)
let pollTimer = null

const typeMap = {
  cr_approved: { label: t('c-notificationbell.s1'), type: 'success' },
  cr_rejected: { label: t('c-notificationbell.s2'), type: 'danger' },
  cr_pending: { label: t('c-notificationbell.s3'), type: 'warning' },
}

function tagType(notificationType) {
  return typeMap[notificationType]?.type || 'info'
}

function tagLabel(notificationType) {
  return typeMap[notificationType]?.label || notificationType || '未知'
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function fetchUnreadCount() {
  try {
    const res = await notificationApi.unreadCount()
    unreadCount.value = res.count ?? res.data?.count ?? 0
  } catch {
    // ignore
  }
}

async function fetchNotifications() {
  loading.value = true
  try {
    const res = await notificationApi.list()
    notifications.value = res.notifications ?? res.data?.notifications ?? []
  } catch {
    notifications.value = []
  } finally {
    loading.value = false
  }
}

async function handleMarkRead(item) {
  if (item.is_read) return
  try {
    await notificationApi.markRead(item.id)
    item.is_read = true
    await fetchUnreadCount()
  } catch {
    // ignore
  }
}

function handleClickItem(item) {
  handleMarkRead(item)
  if (item.type === 'cr_pending' || item.type === 'cr_approved' || item.type === 'cr_rejected') {
    router.push('/admin?tab=change-requests')
  }
}

async function handleMarkAllRead() {
  try {
    await notificationApi.markAllRead()
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
  } catch {
    // ignore
  }
}

function onDropdownVisibleChange(visible) {
  if (visible) {
    fetchNotifications()
  }
}

function startPolling() {
  fetchUnreadCount()
  pollTimer = setInterval(fetchUnreadCount, 30000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<style scoped>
.notification-trigger-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.notification-trigger-wrap .t-badge {
  top: -2px;
  right: -4px;
}
.notification-trigger-wrap .t-badge-dot {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--cinnabar);
}

.notification-badge {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.bell-icon {
  color: var(--olive-gray);
  transition: color var(--transition-fast);
}

.bell-icon:hover {
  color: var(--gold);
}

.notification-dropdown {
  width: 340px;
  max-height: 420px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12);
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f0ebe0;
}

.notification-title {
  font-size: 14px;
  font-weight: 600;
  color: #2c2416;
}

.notification-loading,
.notification-empty {
  padding: 32px 16px;
  text-align: center;
  font-size: 13px;
  color: #999;
}

.notification-list {
  overflow-y: auto;
  flex: 1;
}

.notification-item {
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f5f2ec;
}

.notification-item:hover {
  background: #f8f5f0;
}

.notification-item.unread {
  background: #fdfcfa;
  border-left: 3px solid var(--cinnabar);
}

.notification-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.notification-item-body {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-item-title {
  font-size: 13px;
  font-weight: 500;
  color: #2c2416;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-item-time {
  font-size: 11px;
  color: #aaa;
}
</style>
