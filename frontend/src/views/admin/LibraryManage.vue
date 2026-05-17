<template>
  <LibraryDetail v-if="libraryId" :library-id="libraryId" :embedded="true" />
</template>

<script setup>
defineProps({
  libraryId: { type: [Number, String], required: true }
})

import LibraryDetail from '../LibraryDetail.vue'
</script>
