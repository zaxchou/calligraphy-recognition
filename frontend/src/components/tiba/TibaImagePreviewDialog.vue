<template>
  <el-dialog
    v-model="localVisible"
    title="图片预览"
    width="600px"
    :close-on-click-modal="true"
  >
    <img :src="imageUrl" style="width: 100%;" />
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  imageUrl: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const localVisible = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  localVisible.value = val
})

watch(localVisible, (val) => {
  emit('update:modelValue', val)
})
</script>
