<template>
  <div class="at-timeline">
    <div v-for="item in timelineItems" :key="item.artist.id" class="at-item">
      <div class="at-dot" />
      <div class="at-card" @click="$emit('select', item.artist.name)">
        <div class="at-era">{{ item.artist.dynasty || '未知' }}</div>
        <div class="at-name">{{ item.artist.name }}</div>
        <div class="at-years">
          <template v-if="item.artist.birth_year || item.artist.death_year">
            {{ item.artist.birth_year || '?' }} – {{ item.artist.death_year || '?' }}
          </template>
          <template v-else>生卒年不详</template>
        </div>
        <div v-if="item.artist.alias" class="at-alias">{{ item.artist.alias }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  artists: { type: Array, default: () => [] },
})

defineEmits(['select'])

const timelineItems = computed(() => {
  return [...props.artists]
    .sort((a, b) => {
      const ay = a.birth_year || 9999
      const by = b.birth_year || 9999
      return ay - by
    })
    .map(a => ({ artist: a }))
})
</script>

<style scoped>
.at-timeline {
  position: relative;
  padding-left: 60px;
}

.at-timeline::before {
  content: '';
  position: absolute;
  left: 27px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, #dbbca8, #c45a3c, #dbbca8);
  border-radius: 1px;
}

.at-item {
  position: relative;
  margin-bottom: 16px;
}

.at-dot {
  position: absolute;
  left: -36px;
  top: 20px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #c45a3c;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #dbbca8;
  z-index: 1;
}

.at-card {
  background: #fff;
  border: 1px solid #edeae1;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.at-card:hover {
  border-color: #dbbca8;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.at-era {
  font-size: 0.7rem;
  color: #c45a3c;
  letter-spacing: 0.1em;
  margin-bottom: 4px;
}

.at-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1rem;
  font-weight: 500;
  color: #3a3222;
}

.at-years {
  font-size: 0.75rem;
  color: #a09b8e;
  margin-top: 2px;
}

.at-alias {
  font-size: 0.72rem;
  color: #8a8578;
  margin-top: 2px;
}
</style>
