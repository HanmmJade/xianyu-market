<template>
  <div
    class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
    @click="$emit('click')"
  >
    <!-- 球拍缩略图 -->
    <div v-if="model.image" class="h-40 bg-gray-50 overflow-hidden">
      <img
        :src="model.image"
        :alt="model.model"
        class="w-full h-full object-contain"
      />
    </div>

    <div class="p-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs px-2 py-1 rounded" :class="brandClass">
          {{ brand }}
        </span>
        <span class="text-sm text-gray-500">{{ model.total_sales }}笔成交</span>
      </div>

      <h3 class="text-lg font-semibold mb-2">{{ model.model }}</h3>

      <div class="grid grid-cols-3 gap-2 text-sm">
        <div>
          <div class="text-gray-500">均价</div>
          <div class="font-bold text-blue-600">¥{{ model.avg_price }}</div>
        </div>
        <div>
          <div class="text-gray-500">最低</div>
          <div class="font-bold text-green-600">¥{{ model.min_price }}</div>
        </div>
        <div>
          <div class="text-gray-500">最高</div>
          <div class="font-bold text-red-600">¥{{ model.max_price }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
})

defineEmits(['click'])

const brand = computed(() => {
  const name = props.model.model
  if (name.includes('天斧') || name.includes('弓箭') || name.includes('疾光') || name.includes('双刃')) {
    return 'YONEX'
  }
  if (name.includes('雷霆') || name.includes('战戟') || name.includes('风刃') || name.includes('能量')) {
    return '李宁'
  }
  if (name.includes('神速') || name.includes('龙牙') || name.includes('极速') || name.includes('亮剑')) {
    return 'VICTOR'
  }
  return '其他'
})

const brandClass = computed(() => {
  switch (brand.value) {
    case 'YONEX':
      return 'bg-red-100 text-red-800'
    case '李宁':
      return 'bg-blue-100 text-blue-800'
    case 'VICTOR':
      return 'bg-green-100 text-green-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
})
</script>
