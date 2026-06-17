<template>
  <span :class="className">{{ displayValue }}</span>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({
  to: { type: Number, default: 0 },
  from: { type: Number, default: 0 },
  duration: { type: Number, default: 1.5 },
  separator: { type: String, default: '' },
  className: { type: String, default: '' },
})

const displayValue = ref(formatNumber(props.from))

function formatNumber(value) {
  if (props.separator) {
    return Math.round(value).toLocaleString('en-US').replace(/,/g, props.separator)
  }
  return Math.round(value).toString()
}

function animate(target) {
  const start = parseFloat(displayValue.value.replace(/[^0-9.-]/g, '')) || 0
  const diff = target - start
  const startTime = performance.now()
  const durationMs = props.duration * 1000

  function step(currentTime) {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / durationMs, 1)
    // easeOutQuad
    const eased = 1 - (1 - progress) * (1 - progress)
    const current = start + diff * eased
    displayValue.value = formatNumber(current)

    if (progress < 1) {
      requestAnimationFrame(step)
    }
  }

  requestAnimationFrame(step)
}

onMounted(() => {
  if (props.to > 0) {
    animate(props.to)
  }
})

watch(() => props.to, (newVal) => {
  if (newVal > 0) {
    animate(newVal)
  }
})
</script>
