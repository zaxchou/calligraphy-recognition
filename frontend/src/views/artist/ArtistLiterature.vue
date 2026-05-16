<template>
  <div class="artist-sub-page">
    <div class="asp-header">
      <h2><router-link :to="artistUrl" class="asp-back-link">{{ artistName }}</router-link> 的文献</h2>
    </div>
    <div class="asp-sub-nav">
      <router-link :to="artistUrl" class="asp-nav-item">概览</router-link>
      <router-link :to="artistUrl + '/works'" class="asp-nav-item">作品</router-link>
      <router-link :to="artistUrl + '/seals'" class="asp-nav-item">印章</router-link>
      <router-link :to="artistUrl + '/literature'" class="asp-nav-item active">文献</router-link>
      <router-link :to="artistUrl + '/analysis'" class="asp-nav-item">分析</router-link>
    </div>
    <div class="asp-empty">文献著录功能开发中，敬请期待</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const artistName = route.params.name
const artistUrl = computed(() => '/artist/' + encodeURIComponent(artistName))
</script>

<style scoped>
.artist-sub-page { max-width: 1100px; margin: 0 auto; padding: 24px 20px; }
.asp-header h2 { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0 0 16px; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-empty { text-align: center; padding: 80px 0; color: #b0a890; font-size: 16px; }
</style>
