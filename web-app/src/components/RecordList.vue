<template>
  <div class="bg-white rounded-lg shadow-md p-4">
    <h3 class="text-lg font-semibold mb-4">成交记录</h3>
    <div class="overflow-x-auto">
      <table class="min-w-full">
        <thead>
          <tr class="border-b">
            <th class="text-left py-2 px-3">标题</th>
            <th class="text-right py-2 px-3">价格</th>
            <th class="text-center py-2 px-3">成色</th>
            <th class="text-center py-2 px-3">评分</th>
            <th class="text-center py-2 px-3">时间</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="record in records"
            :key="record.id"
            class="border-b hover:bg-gray-50"
          >
            <td class="py-2 px-3 max-w-xs truncate">{{ record.title }}</td>
            <td class="py-2 px-3 text-right font-bold text-blue-600">
              ¥{{ record.price }}
            </td>
            <td class="py-2 px-3 text-center">
              <span
                class="px-2 py-1 rounded text-xs"
                :class="getConditionBadge(record.condition_inferred || record.condition)"
              >
                {{ record.condition_inferred || record.condition || '未知' }}
              </span>
            </td>
            <td class="py-2 px-3 text-center">
              <div v-if="record.condition_score" class="flex items-center justify-center">
                <div class="w-16 bg-gray-200 rounded-full h-2 mr-2">
                  <div
                    class="h-2 rounded-full"
                    :class="getScoreColor(record.condition_score)"
                    :style="{ width: record.condition_score + '%' }"
                  ></div>
                </div>
                <span class="text-sm">{{ record.condition_score }}</span>
              </div>
              <span v-else class="text-gray-400">-</span>
            </td>
            <td class="py-2 px-3 text-center text-sm text-gray-500">
              {{ record.sold_time || record.crawled_at?.split('T')[0] || '-' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  records: {
    type: Array,
    default: () => [],
  },
})

const getConditionBadge = (condition) => {
  if (!condition) return 'bg-gray-100 text-gray-800'
  if (condition.includes('全新') || condition.includes('95')) {
    return 'bg-green-100 text-green-800'
  }
  if (condition.includes('9新')) {
    return 'bg-blue-100 text-blue-800'
  }
  if (condition.includes('85') || condition.includes('8新')) {
    return 'bg-yellow-100 text-yellow-800'
  }
  return 'bg-gray-100 text-gray-800'
}

const getScoreColor = (score) => {
  if (score >= 80) return 'bg-green-500'
  if (score >= 60) return 'bg-blue-500'
  if (score >= 40) return 'bg-yellow-500'
  return 'bg-red-500'
}
</script>
