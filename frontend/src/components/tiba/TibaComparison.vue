<template>
  <el-card shadow="hover" class="comparison-dashboard-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">名家对比</span>
      </div>
    </template>
    <div class="comparison-bars-container">
      <!-- 画家选择器 -->
      <div class="comparison-header">
        <div class="artist-select-wrap">
          <el-select v-model="leftArtist" size="small" class="artist-select">
            <el-option
              v-for="name in artistOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
          <div class="artist-avatar" :style="avatarStyle(leftArtist)">
            {{ leftArtist ? leftArtist.charAt(0) : '?' }}
          </div>
        </div>
        <div class="vs-divider">VS</div>
        <div class="artist-select-wrap right">
          <div class="artist-avatar" :style="avatarStyle(rightArtist)">
            {{ rightArtist ? rightArtist.charAt(0) : '?' }}
          </div>
          <el-select v-model="rightArtist" size="small" class="artist-select">
            <el-option
              v-for="name in artistOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </div>
      </div>

      <!-- 对比条 -->
      <div class="comparison-bars" v-if="leftStats && rightStats">
        <TibaComparisonBar
          v-for="item in visibleComparisonItems"
          :key="item.label"
          :label="item.label"
          :left-value="item.leftValue"
          :left-percent="item.leftPercent"
          :right-value="item.rightValue"
          :right-percent="item.rightPercent"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import TibaComparisonBar from './TibaComparisonBar.vue'

const props = defineProps({
  historyList: {
    type: Array,
    default: () => []
  }
})

// 从数据中抽取所有画家名
const artistOptions = computed(() => {
  const set = new Set()
  props.historyList.forEach(item => {
    if (item.artist) set.add(item.artist)
  })
  return Array.from(set)
})

// 默认左=李鱓，右=郑燮；若数据中不存在则自动回退到可用选项
const leftArtist = ref('李鱓')
const rightArtist = ref('郑燮')

watch(artistOptions, (options) => {
  if (options.length === 0) return
  if (!options.includes(leftArtist.value)) {
    leftArtist.value = options[0]
  }
  if (!options.includes(rightArtist.value) || leftArtist.value === rightArtist.value) {
    const remaining = options.filter(o => o !== leftArtist.value)
    rightArtist.value = remaining[0] || options[0]
  }
}, { immediate: true })

// 头像颜色映射（根据名字哈希）
const avatarColors = [
  'linear-gradient(135deg, #c96442 0%, #a84e30 100%)',
  'linear-gradient(135deg, #4a90d9 0%, #2c5f7c 100%)',
  'linear-gradient(135deg, #20b2aa 0%, #008b8b 100%)',
  'linear-gradient(135deg, #b8a47e 0%, #9a855e 100%)',
  'linear-gradient(135deg, #8e7cc3 0%, #6b5b95 100%)',
  'linear-gradient(135deg, #e67e22 0%, #d35400 100%)',
]
function avatarStyle(name) {
  if (!name) return {}
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  const idx = Math.abs(hash) % avatarColors.length
  return { background: avatarColors[idx] }
}

// 统计计算
const total = computed(() => props.historyList.length)

const avg = (arr, key) => {
  const nums = arr.map(item => Number(item[key])).filter(n => Number.isFinite(n))
  if (nums.length === 0) return 0
  return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10
}

const getFormTypes = (item) => {
  return item?.positionAnalysis?.form_types || item?.position_analysis?.form_types || []
}
const getOverlapRatio = (item) => {
  const ratio = item?.positionAnalysis?.overlap_ratio ?? item?.position_analysis?.overlap_ratio
  return Number.isFinite(ratio) ? ratio : 0
}

const calcFormRichness = (arr) => {
  const counts = arr.map(item => {
    const formTypes = getFormTypes(item)
    return formTypes.filter(ft => ft.matched).length
  }).filter(n => n > 0)
  if (counts.length === 0) return 0
  return Math.round((counts.reduce((a, b) => a + b, 0) / counts.length) * 10) / 10
}

const calcDominantFormPercent = (arr) => {
  if (arr.length === 0) return { name: '-', percent: 0 }
  const typeCounts = {}
  arr.forEach(item => {
    const formTypes = getFormTypes(item)
    formTypes.filter(ft => ft.matched).forEach(ft => {
      typeCounts[ft.name] = (typeCounts[ft.name] || 0) + 1
    })
  })
  let maxCount = 0
  let dominantName = '-'
  Object.entries(typeCounts).forEach(([name, count]) => {
    if (count > maxCount) {
      maxCount = count
      dominantName = name
    }
  })
  const percent = arr.length > 0 ? Math.round((maxCount / arr.length) * 1000) / 10 : 0
  return { name: dominantName, percent }
}

const calcInvasionPercent = (arr) => {
  const ratios = arr.map(item => getOverlapRatio(item)).filter(r => r > 0)
  if (ratios.length === 0) return 0
  return Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 1000) / 10
}

const build = (arr) => {
  const count = arr.length
  const countPercent = total.value > 0 ? (count / total.value) * 100 : 0
  const fmt = (n) => `${Number(n).toFixed(1).replace(/\.0$/, '')}%`
  const formRichness = calcFormRichness(arr)
  const dominantForm = calcDominantFormPercent(arr)
  const invasionPercent = calcInvasionPercent(arr)

  return {
    count, countPercent,
    avgInscription: avg(arr, 'inscriptionPercent'),
    avgPainting: avg(arr, 'paintingPercent'),
    avgBlank: avg(arr, 'blankPercent'),
    formRichness,
    formRichnessDisplay: `${formRichness} 种/幅`,
    dominantFormName: dominantForm.name,
    dominantFormPercent: dominantForm.percent,
    dominantFormDisplay: `${dominantForm.name} ${dominantForm.percent}%`,
    invasionPercent,
    invasionDisplay: fmt(invasionPercent)
  }
}

const leftStats = computed(() => {
  const data = props.historyList.filter(item => item.artist === leftArtist.value)
  return build(data)
})

const rightStats = computed(() => {
  const data = props.historyList.filter(item => item.artist === rightArtist.value)
  return build(data)
})

const comparisonItems = computed(() => [
  {
    label: '画作数量',
    leftValue: leftStats.value.count,
    leftPercent: leftStats.value.countPercent,
    rightValue: rightStats.value.count,
    rightPercent: rightStats.value.countPercent,
    visible: true
  },
  {
    label: '平均题跋占比',
    leftValue: leftStats.value.avgInscription.toFixed(1) + '%',
    leftPercent: leftStats.value.avgInscription,
    rightValue: rightStats.value.avgInscription.toFixed(1) + '%',
    rightPercent: rightStats.value.avgInscription,
    visible: true
  },
  {
    label: '平均绘画占比',
    leftValue: leftStats.value.avgPainting.toFixed(1) + '%',
    leftPercent: leftStats.value.avgPainting,
    rightValue: rightStats.value.avgPainting.toFixed(1) + '%',
    rightPercent: rightStats.value.avgPainting,
    visible: leftStats.value.avgPainting > 0 || rightStats.value.avgPainting > 0
  },
  {
    label: '平均留白占比',
    leftValue: leftStats.value.avgBlank.toFixed(1) + '%',
    leftPercent: leftStats.value.avgBlank,
    rightValue: rightStats.value.avgBlank.toFixed(1) + '%',
    rightPercent: rightStats.value.avgBlank,
    visible: leftStats.value.avgBlank > 0 || rightStats.value.avgBlank > 0
  },
  {
    label: '形式丰富度',
    leftValue: leftStats.value.formRichnessDisplay,
    leftPercent: leftStats.value.formRichness * 20,
    rightValue: rightStats.value.formRichnessDisplay,
    rightPercent: rightStats.value.formRichness * 20,
    visible: true
  },
  {
    label: '主导形式占比',
    leftValue: leftStats.value.dominantFormDisplay,
    leftPercent: leftStats.value.dominantFormPercent,
    rightValue: rightStats.value.dominantFormDisplay,
    rightPercent: rightStats.value.dominantFormPercent,
    visible: true
  },
  {
    label: '题跋侵入度',
    leftValue: leftStats.value.invasionDisplay,
    leftPercent: leftStats.value.invasionPercent,
    rightValue: rightStats.value.invasionDisplay,
    rightPercent: rightStats.value.invasionPercent,
    visible: true
  }
])

const visibleComparisonItems = computed(() => comparisonItems.value.filter(item => item.visible))
</script>

<style scoped>
.comparison-dashboard-card {
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
}

.comparison-dashboard-card :deep(.el-card__header) {
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
}

.comparison-bars-container {
  padding: 16px 20px;
}

.comparison-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.artist-select-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.artist-select-wrap.right {
  flex-direction: row-reverse;
}

.artist-select {
  width: 100px;
}

.artist-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  font-weight: bold;
  font-family: "KaiTi", "STKaiti", serif;
  flex-shrink: 0;
}

.vs-divider {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
  letter-spacing: 1px;
}

.comparison-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comparison-dashboard-card .card-header {
  flex-wrap: nowrap;
  white-space: nowrap;
}

.comparison-dashboard-card .card-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

@media (max-width: 768px) {
  .comparison-bars-container {
    padding: 20px 16px;
  }

  .comparison-header {
    flex-direction: column;
    gap: 12px;
    margin-bottom: 16px;
  }

  .artist-select-wrap,
  .artist-select-wrap.right {
    width: 100%;
    justify-content: center;
    flex-direction: row;
  }

  .artist-select {
    width: 120px;
  }

  .vs-divider {
    font-size: 14px;
    order: -1;
  }

  .comparison-bars {
    gap: 10px;
  }
}

@media (max-width: 480px) {
  .comparison-bars-container {
    padding: 16px 12px;
  }

  .comparison-header {
    margin-bottom: 14px;
  }

  .artist-select {
    width: 100px;
  }

  .comparison-bars {
    gap: 10px;
  }
}
</style>
