<template>
  <div class="comparison-row">
    <div class="bar-side left-side">
      <div class="bar-track-full">
        <div class="bar-bg"></div>
        <div class="bar-progress li-bar" :style="{ width: leftWidth }">
          <span v-if="leftLabelInside" class="bar-value-text">{{ leftValue }}</span>
        </div>
        <span
          v-if="!leftLabelInside"
          class="bar-value-text bar-value-text-outside left-outside"
          :style="leftLabelStyle"
        >
          {{ leftValue }}
        </span>
      </div>
    </div>
    <div class="bar-label-center">{{ label }}</div>
    <div class="bar-side right-side">
      <div class="bar-track-full">
        <div class="bar-bg"></div>
        <div class="bar-progress zheng-bar" :style="{ width: rightWidth }">
          <span v-if="rightLabelInside" class="bar-value-text">{{ rightValue }}</span>
        </div>
        <span
          v-if="!rightLabelInside"
          class="bar-value-text bar-value-text-outside right-outside"
          :style="rightLabelStyle"
        >
          {{ rightValue }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { percentWidth, shouldLabelInside, outsideLabelStyle } from '../../tiba/utils'

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  leftValue: {
    type: [String, Number],
    required: true
  },
  leftPercent: {
    type: Number,
    required: true
  },
  rightValue: {
    type: [String, Number],
    required: true
  },
  rightPercent: {
    type: Number,
    required: true
  }
})

const leftWidth = computed(() => percentWidth(props.leftPercent))
const rightWidth = computed(() => percentWidth(props.rightPercent))
const leftLabelInside = computed(() => shouldLabelInside(props.leftPercent))
const rightLabelInside = computed(() => shouldLabelInside(props.rightPercent))
const leftLabelStyle = computed(() => outsideLabelStyle(props.leftPercent, 'left'))
const rightLabelStyle = computed(() => outsideLabelStyle(props.rightPercent, 'right'))
</script>

<style scoped>
.comparison-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar-side {
  flex: 1;
  display: flex;
}

.bar-side.left-side {
  justify-content: flex-end;
}

.bar-side.right-side {
  justify-content: flex-start;
}

.bar-label-center {
  width: 80px;
  text-align: center;
  font-size: 12px;
  color: #888;
  flex-shrink: 0;
}

.bar-track-full {
  width: 100%;
  height: 20px;
  position: relative;
  display: flex;
  align-items: center;
}

.bar-bg {
  position: absolute;
  width: 100%;
  height: 100%;
  background: #f0f0f0;
  border-radius: 10px;
}

.bar-progress {
  position: absolute;
  height: 100%;
  border-radius: 10px;
  display: flex;
  align-items: center;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  transform-origin: left center;
  animation: barGrow 0.6s cubic-bezier(0.25, 0.8, 0.25, 1) both;
}

.left-side .bar-progress {
  transform-origin: right center;
}

@keyframes barGrow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.bar-progress.li-bar {
  background: linear-gradient(90deg, #ff6b6b 0%, #ee5a5a 100%);
  right: 0;
  justify-content: flex-start;
  padding-left: 8px;
}

.bar-progress.zheng-bar {
  background: linear-gradient(90deg, #4a90d9 0%, #5ba3d9 100%);
  left: 0;
  justify-content: flex-end;
  padding-right: 8px;
}

.bar-value-text {
  color: white;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.bar-value-text-outside {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  color: #888;
  font-size: 11px;
  font-weight: 500;
  pointer-events: none;
}

.bar-value-text-outside.left-outside {
  text-align: right;
  right: calc(100% + 6px);
}

.bar-value-text-outside.right-outside {
  text-align: left;
  left: calc(100% + 6px);
}

@media (max-width: 768px) {
  .comparison-row {
    gap: 12px;
  }
  
  .bar-track-full {
    height: 28px;
  }
  
  .bar-value-text {
    font-size: 12px;
  }
  
  .bar-label-center {
    width: 80px;
    font-size: 12px;
  }
  
  .bar-progress.li-bar {
    padding-left: 8px;
  }
  
  .bar-progress.zheng-bar {
    padding-right: 8px;
  }
}

@media (max-width: 480px) {
  .comparison-row {
    gap: 8px;
  }
  
  .bar-track-full {
    height: 24px;
  }
  
  .bar-value-text {
    font-size: 11px;
  }
  
  .bar-label-center {
    width: 60px;
    font-size: 11px;
  }
}
</style>
