<template>
  <div class="pn-nav">
    <button
      v-for="group in groups"
      :key="group.letter"
      class="pn-btn"
      :class="{ 'pn-active': activeLetter === group.letter }"
      @click="$emit('select', group.letter)"
    >
      {{ group.letter }}
      <span class="pn-count">{{ group.count }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  groups: { type: Array, default: () => [] },
  activeLetter: { type: String, default: '' },
})

defineEmits(['select'])
</script>

<style scoped>
.pn-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}

.pn-btn {
  position: relative;
  min-width: 32px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid #edeae1;
  border-radius: 6px;
  background: #fff;
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b6b60;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pn-btn:hover {
  border-color: #dbbca8;
  color: #c45a3c;
}

.pn-active {
  background: #c45a3c;
  border-color: #c45a3c;
  color: #fff;
}

.pn-active:hover {
  background: #b54a2d;
  border-color: #b54a2d;
  color: #fff;
}

.pn-count {
  font-size: 0.6rem;
  margin-left: 2px;
  opacity: 0.7;
}
</style>
