<template>
  <div class="bg-white rounded-lg shadow-md p-4">
    <h3 class="text-lg font-semibold mb-4">成色统计</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div
        v-for="item in conditions"
        :key="item.condition"
        class="text-center p-3 rounded-lg"
        :class="getConditionClass(item.condition)"
      >
        <div class="text-sm text-gray-600">{{ item.condition }}</div>
        <div class="text-xl font-bold">{{ item.count }}笔</div>
        <div class="text-sm">均价 ¥{{ item.avg_price }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  conditions: {
    type: Array,
    default: () => [],
  },
})

const getConditionClass = (condition) => {
  if (condition.includes('全新') || condition.includes('95')) {
    return 'bg-green-50'
  }
  if (condition.includes('9新')) {
    return 'bg-blue-50'
  }
  if (condition.includes('85') || condition.includes('8新')) {
    return 'bg-yellow-50'
  }
  return 'bg-gray-50'
}
</script>
