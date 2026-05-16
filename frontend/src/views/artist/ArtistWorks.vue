<template>
  <div class="artist-sub-page">
    <div class="redirect-message">
      <p>正在跳转到「作品库」页面...</p>
      <p class="redirect-hint">已自动筛选画家「{{ artistName }}」</p>
      <a :href="targetUrl" class="redirect-link">立即前往</a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const artistName = route.params.name
const targetUrl = computed(() => `/#/tubi/list?artist=${encodeURIComponent(artistName)}`)

window.location.href = targetUrl.value
</script>

<style scoped>
.artist-sub-page { max-width: 600px; margin: 60px auto; padding: 24px; text-align: center; }
.redirect-message { background: #fff; border: 1px solid #edeae1; border-radius: 12px; padding: 40px; }
.redirect-message p { font-size: 16px; color: #3a3222; margin: 0 0 12px; }
.redirect-hint { font-size: 14px; color: #8a8578; }
.redirect-link { display: inline-block; margin-top: 16px; padding: 10px 28px; background: #c45a3c; color: #fff; border-radius: 6px; text-decoration: none; font-size: 14px; }
.redirect-link:hover { background: #a84a30; }
</style>
