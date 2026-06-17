<template>
  <div style="background: transparent; color: white;">
    <!-- Hero区域 -->
    <div style="display: flex; height: 100vh; padding: 60px 80px;">
      
      <!-- 左侧：信息区 -->
      <div style="width: 45%; display: flex; flex-direction: column; justify-content: center;">
        <!-- TextPressure 标题 -->
        <div style="height: 140px; margin-bottom: 50px;">
          <TextPressure
            text="BADMINTON MARKET"
            :flex="true"
            :alpha="false"
            :stroke="false"
            :width="true"
            :weight="true"
            :italic="true"
            text-color="#ffffff"
            :min-font-size="48"
          />
        </div>

        <div style="margin-bottom: 50px;">
          <div style="display: flex; align-items: baseline; margin-bottom: 20px;">
            <CountUp :to="allModels.length" :duration="2" style="font-size: 56px; font-weight: bold; color: white;" />
            <span style="font-size: 18px; color: #666; margin-left: 16px;">个型号</span>
          </div>
          <div style="display: flex; align-items: baseline; margin-bottom: 20px;">
            <CountUp :to="modelsWithData.length" :duration="2" style="font-size: 56px; font-weight: bold; color: white;" />
            <span style="font-size: 18px; color: #666; margin-left: 16px;">有数据</span>
          </div>
          <div style="display: flex; align-items: baseline;">
            <CountUp :to="stats.total_records" :duration="2" separator="," style="font-size: 56px; font-weight: bold; color: white;" />
            <span style="font-size: 18px; color: #666; margin-left: 16px;">条记录</span>
          </div>
        </div>

        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索型号..."
          class="cursor-target"
          style="width: 100%; max-width: 450px; padding: 16px 20px; background: transparent; border: 1px solid #333; border-radius: 8px; color: white; font-size: 16px; outline: none; margin-bottom: 24px;"
        />

        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <button
            v-for="brand in brandOptions"
            :key="brand.value"
            class="cursor-target"
            style="padding: 10px 24px; border-radius: 999px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s;"
            :style="selectedBrand === brand.value ? 'background: white; color: black; border: none;' : 'background: transparent; color: #999; border: 1px solid #555;'"
            @click="selectedBrand = brand.value"
          >
            {{ brand.label }}
          </button>
        </div>
      </div>

      <!-- 右侧：CardSwap轮播区 -->
      <div style="width: 55%; display: flex; align-items: center; justify-content: center;">
        <div style="position: relative; width: 550px; height: 450px;">
          <CardSwap
            v-if="topModels.length >= 3"
            :width="500"
            :height="380"
            :card-distance="120"
            :vertical-distance="110"
            :delay="4000"
            :pause-on-hover="true"
            :skew-amount="0"
            easing="linear"
          >
            <Card v-for="model in topModels" :key="model.name" custom-class="card-custom">
              <div style="display: flex; height: 100%; background: rgba(10, 10, 10, 0.85); border: 1px solid #333; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.5); backdrop-filter: blur(20px);">
                <div style="width: 50%; height: 100%; background: rgba(0, 0, 0, 0.5); display: flex; align-items: center; justify-content: center; overflow: hidden;">
                  <img v-if="model.image" :src="model.image" :alt="model.name" style="width: 100%; height: 100%; object-fit: cover;" />
                  <div v-else style="color: #333; font-size: 12px;">暂无图片</div>
                </div>
                <div style="width: 50%; padding: 28px; display: flex; flex-direction: column; justify-content: space-between;">
                  <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                      <span style="font-size: 11px; padding: 4px 12px; background: rgba(255,255,255,0.1); border-radius: 4px; color: #888;">{{ model.brand }}</span>
                      <span style="font-size: 13px; color: #555;">{{ model.total_sales }}笔</span>
                    </div>
                    <h3 style="font-size: 24px; font-weight: bold; color: white; margin-bottom: 8px;">{{ model.name }}</h3>
                    <p v-if="model.aliases?.length" style="font-size: 12px; color: #444;">{{ model.aliases[0] }}</p>
                  </div>
                  <div style="margin-top: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                      <div>
                        <div style="font-size: 12px; color: #555; margin-bottom: 4px;">均价</div>
                        <div style="font-size: 36px; font-weight: bold; color: white;">¥{{ model.avg_price }}</div>
                      </div>
                      <div style="text-align: right;">
                        <div style="font-size: 12px; color: #555; margin-bottom: 4px;">区间</div>
                        <div style="font-size: 14px; color: #666;">¥{{ model.min_price }} - ¥{{ model.max_price }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </CardSwap>
        </div>
      </div>
    </div>

    <!-- 分隔线 -->
    <div style="border-top: 1px solid #1a1a1a; margin: 0 80px;"></div>

    <!-- 型号列表区域 -->
    <div style="padding: 60px 80px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px;">
        <h2 style="font-size: 18px; color: #666;">全部型号</h2>
        <div style="display: flex; gap: 8px;">
          <button 
            class="cursor-target"
            style="padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;"
            :style="showAll ? 'background: white; color: black;' : 'color: #666;'"
            @click="showAll = true"
          >全部</button>
          <button 
            class="cursor-target"
            style="padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;"
            :style="!showAll ? 'background: white; color: black;' : 'color: #666;'"
            @click="showAll = false"
          >有数据</button>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;">
        <div
          v-for="model in filteredModels"
          :key="model.name"
          class="cursor-target"
          style="background: rgba(10, 10, 10, 0.8); border: 1px solid #1a1a1a; border-radius: 10px; overflow: hidden; cursor: pointer; transition: border-color 0.2s; backdrop-filter: blur(10px);"
          :style="{ opacity: model.has_data ? 1 : 0.4 }"
          @click="goToDetail(model)"
          @mouseenter="$event.target.style.borderColor = '#333'"
          @mouseleave="$event.target.style.borderColor = '#1a1a1a'"
        >
          <div style="height: 120px; background: rgba(0, 0, 0, 0.5); display: flex; align-items: center; justify-content: center; overflow: hidden;">
            <img v-if="model.image" :src="model.image" :alt="model.name" style="max-width: 100%; max-height: 100%; object-fit: contain;" />
            <span v-else style="color: #222; font-size: 11px;">无图片</span>
          </div>
          <div style="padding: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span style="font-size: 10px; color: #555;">{{ model.brand }}</span>
              <span v-if="model.has_data" style="font-size: 10px; color: #444;">有数据</span>
            </div>
            <h3 style="font-size: 13px; font-weight: 500; color: white; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ model.name }}</h3>
            <div v-if="model.has_data" style="font-size: 11px; color: #555;">均价 ¥{{ model.avg_price }}</div>
            <div v-else style="font-size: 11px; color: #333;">待采集</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" style="position: fixed; inset: 0; background: rgba(0, 0, 0, 0.8); display: flex; align-items: center; justify-content: center; z-index: 50; backdrop-filter: blur(10px);">
      <div style="color: #666; font-size: 18px;">加载中...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRacketDatabase, getStats } from '../api'
import CountUp from '../components/vue-bits/CountUp.vue'
import CardSwap, { Card } from '../components/vue-bits/CardSwap.vue'
import TextPressure from '../components/vue-bits/TextPressure.vue'

const router = useRouter()
const allModels = ref([])
const stats = ref({ total_records: 0, total_models: 0, last_crawled: null })
const selectedBrand = ref('全部')
const searchQuery = ref('')
const showAll = ref(true)
const loading = ref(true)

const modelsWithData = computed(() => allModels.value.filter(m => m.has_data))

const topModels = computed(() => {
  return [...allModels.value]
    .filter(m => m.has_data && m.total_sales > 0)
    .sort((a, b) => b.total_sales - a.total_sales)
    .slice(0, 5)
})

const brandOptions = computed(() => {
  const brands = { '全部': allModels.value.length }
  allModels.value.forEach(m => { brands[m.brand] = (brands[m.brand] || 0) + 1 })
  return Object.entries(brands).map(([brand]) => ({ value: brand, label: brand }))
})

const filteredModels = computed(() => {
  let result = allModels.value
  if (selectedBrand.value !== '全部') result = result.filter(m => m.brand === selectedBrand.value)
  if (!showAll.value) result = result.filter(m => m.has_data)
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(m => m.name.toLowerCase().includes(query) || m.aliases?.some(a => a.toLowerCase().includes(query)))
  }
  return result
})

const goToDetail = (model) => {
  router.push({ name: 'ModelDetail', params: { name: model.name } })
}

onMounted(async () => {
  try {
    const [dbRes, statsRes] = await Promise.all([getRacketDatabase(), getStats()])
    allModels.value = dbRes.data
    stats.value = statsRes.data
  } catch (error) {
    console.error('Failed to load data:', error)
  } finally {
    loading.value = false
  }
})
</script>

<style>
.card-custom {
  border: none !important;
  background: transparent !important;
}
</style>
