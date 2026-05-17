<template>
  <div class="artist-card" @click="$emit('click')">
    <div class="ac-avatar">
      <img v-if="artist.avatar_url" :src="artist.avatar_url" class="ac-avatar-img" referrerpolicy="no-referrer" />
      <span v-else class="ac-avatar-text">{{ artist.name.charAt(0) }}</span>
    </div>
    <div class="ac-info">
      <div class="ac-name">{{ artist.name }}</div>
      <div v-if="artist.alias" class="ac-alias">{{ artist.alias }}</div>
      <div class="ac-years">
        {{ artist.birth_year || '?' }}{{ artist.death_year ? ' – ' + artist.death_year : '' }}
      </div>
      <div class="ac-tags">
        <span v-if="artist.dynasty" class="ac-tag ac-tag-dynasty">{{ artist.dynasty }}</span>
        <span v-if="artist.art_school" class="ac-tag ac-tag-school">{{ artist.art_school }}</span>
      </div>
      <div v-if="artist.summary" class="ac-summary">{{ artist.summary }}</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  artist: { type: Object, required: true },
})

defineEmits(['click'])
</script>

<style scoped>
.artist-card {
  display: flex;
  gap: 14px;
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid #edeae1;
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.03);
  position: relative;
  overflow: hidden;
}

.artist-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.07);
  border-color: #dbbca8;
}

.artist-card:hover .ac-summary {
  opacity: 1;
  max-height: 60px;
}

.ac-avatar {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ac-avatar-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}

.ac-avatar-text {
  color: #fff;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.2rem;
  font-weight: 500;
}

.ac-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ac-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1rem;
  font-weight: 500;
  color: #3a3222;
}

.ac-alias {
  font-size: 0.75rem;
  color: #8a8578;
}

.ac-years {
  font-size: 0.75rem;
  color: #a09b8e;
  margin-top: 2px;
}

.ac-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 3px;
}

.ac-tag {
  display: inline-block;
  font-size: 0.68rem;
  padding: 1px 8px;
  border-radius: 999px;
  letter-spacing: 0.04em;
}

.ac-tag-dynasty {
  background: #f5f0ea;
  color: #8a6f4c;
}

.ac-tag-school {
  background: #f0ede8;
  color: #6b6b60;
}

.ac-summary {
  font-size: 0.72rem;
  color: #9a9588;
  line-height: 1.5;
  margin-top: 6px;
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  transition: all 0.3s ease;
}
</style>
