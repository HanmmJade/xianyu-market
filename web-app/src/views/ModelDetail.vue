<template>
  <div style="min-height: 100vh; background: #000; color: white; padding: 40px 80px;">
    <!-- 返回按钮 -->
    <button
      class="cursor-target"
      style="display: flex; align-items: center; color: #666; font-size: 14px; margin-bottom: 40px; cursor: pointer; background: none; border: none;"
      @click="router.push('/')"
    >
      <svg style="width: 20px; height: 20px; margin-right: 8px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 19l-7-7 7-7" />
      </svg>
      返回
    </button>

    <!-- 加载状态 -->
    <div v-if="loading" style="text-align: center; padding: 80px 0;">
      <div style="color: #555;">加载中...</div>
    </div>

    <template v-else-if="detail">
      <div style="display: flex; gap: 60px; margin-bottom: 80px;">
        <!-- 左侧：图片 -->
        <div v-if="detail.image" style="width: 40%; background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 16px; overflow: hidden;">
          <img :src="detail.image" :alt="name" style="width: 100%; height: 400px; object-fit: contain;" />
        </div>

        <!-- 右侧：信息 -->
        <div style="flex: 1; display: flex; flex-direction: column; justify-content: center;">
          <h1 style="font-size: 48px; font-weight: bold; color: white; margin-bottom: 40px;">{{ name }}</h1>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 40px;">
            <div>
              <CountUp :to="detail.records?.length || 0" :duration="1.5" style="font-size: 48px; font-weight: bold; color: white;" />
              <div style="font-size: 14px; color: #555; margin-top: 8px;">总成交量</div>
            </div>
            <div>
              <div style="display: flex; align-items: baseline;">
                <span style="font-size: 24px; color: #666;">¥</span>
                <CountUp :to="currentAvgPrice" :duration="1.5" separator="," style="font-size: 48px; font-weight: bold; color: white;" />
              </div>
              <div style="font-size: 14px; color: #555; margin-top: 8px;">当前均价</div>
            </div>
            <div>
              <div style="font-size: 32px; font-weight: bold; color: white;">¥{{ minPrice }}</div>
              <div style="font-size: 14px; color: #555; margin-top: 8px;">最低价</div>
            </div>
            <div>
              <div style="font-size: 32px; font-weight: bold; color: white;">¥{{ maxPrice }}</div>
              <div style="font-size: 14px; color: #555; margin-top: 8px;">最高价</div>
            </div>
          </div>

          <div style="font-size: 14px; color: #555;">数据点: {{ trend.length }} 天</div>
        </div>
      </div>

      <!-- 价格走势 -->
      <div style="margin-bottom: 60px;">
        <PriceChart :data="trend" />
      </div>

      <!-- 成色统计 -->
      <div style="margin-bottom: 60px;">
        <ConditionStats :conditions="detail.by_condition" />
      </div>

      <!-- 成交记录 -->
      <RecordList :records="detail.records" />
    </template>

    <!-- 错误状态 -->
    <div v-else style="text-align: center; padding: 80px 0; color: #555;">
      未找到型号数据
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getModelDetail, getModelTrend } from '../api'
import ConditionStats from '../components/ConditionStats.vue'
import PriceChart from '../components/PriceChart.vue'
import RecordList from '../components/RecordList.vue'
import CountUp from '../components/vue-bits/CountUp.vue'

const router = useRouter()
const route = useRoute()
const name = route.params.name
const detail = ref(null)
const trend = ref([])
const loading = ref(true)

const currentAvgPrice = computed(() => {
  if (trend.value.length > 0) return trend.value[0].avg_price
  if (detail.value?.records?.length > 0) {
    const total = detail.value.records.reduce((sum, r) => sum + r.price, 0)
    return Math.round(total / detail.value.records.length)
  }
  return 0
})

const minPrice = computed(() => {
  if (detail.value?.records?.length > 0) return Math.min(...detail.value.records.map(r => r.price))
  return 0
})

const maxPrice = computed(() => {
  if (detail.value?.records?.length > 0) return Math.max(...detail.value.records.map(r => r.price))
  return 0
})

onMounted(async () => {
  try {
    const [detailRes, trendRes] = await Promise.all([getModelDetail(name), getModelTrend(name)])
    detail.value = detailRes.data
    trend.value = trendRes.data
  } catch (error) {
    console.error('Failed to load model detail:', error)
  } finally {
    loading.value = false
  }
})
</script>
