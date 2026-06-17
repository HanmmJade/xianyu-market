<template>
  <div class="bg-white rounded-lg shadow-md p-4">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold">价格走势</h3>
      <span v-if="data.length < 3" class="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
        数据积累中
      </span>
    </div>

    <!-- 有数据时显示图表 -->
    <v-chart v-if="data.length > 0" :option="chartOption" :style="{ height: '300px' }" autoresize />

    <!-- 无数据时显示空状态 -->
    <div v-else class="h-[300px] flex items-center justify-center text-gray-400">
      <div class="text-center">
        <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
        </svg>
        <p>暂无价格数据</p>
        <p class="text-sm mt-1">数据采集后将自动显示</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent])

const props = defineProps({
  data: {
    type: Array,
    default: () => [],
  },
})

const chartOption = computed(() => {
  const dates = props.data.map((item) => item.date)
  const avgPrices = props.data.map((item) => item.avg_price)
  const minPrices = props.data.map((item) => item.min_price)
  const maxPrices = props.data.map((item) => item.max_price)
  const counts = props.data.map((item) => item.count || 0)

  return {
    tooltip: {
      trigger: 'axis',
      formatter: function (params) {
        let result = `<div style="font-weight:bold;margin-bottom:4px">${params[0].axisValue}</div>`
        params.forEach((item) => {
          const color = item.color
          result += `<div style="display:flex;align-items:center;gap:4px">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
            <span>${item.seriesName}: ¥${item.value}</span>
          </div>`
        })
        // 显示成交量
        const idx = params[0].dataIndex
        if (counts[idx] > 0) {
          result += `<div style="margin-top:4px;color:#666;font-size:12px">成交量: ${counts[idx]}笔</div>`
        }
        return result
      },
    },
    legend: {
      data: ['均价', '最低价', '最高价'],
      top: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: {
        rotate: dates.length > 7 ? 45 : 0,
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '¥{value}',
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#E5E7EB',
        },
      },
    },
    series: [
      {
        name: '均价',
        type: 'line',
        data: avgPrices,
        smooth: dates.length > 2,
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#3B82F6' },
        lineStyle: { width: 3 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.2)' },
              { offset: 1, color: 'rgba(59,130,246,0)' },
            ],
          },
        },
        markPoint: dates.length > 1 ? {
          data: [
            { type: 'max', name: '最高均价' },
            { type: 'min', name: '最低均价' },
          ],
        } : undefined,
      },
      {
        name: '最低价',
        type: 'line',
        data: minPrices,
        smooth: dates.length > 2,
        symbol: 'diamond',
        symbolSize: 6,
        lineStyle: { type: 'dashed', width: 1.5 },
        itemStyle: { color: '#10B981' },
      },
      {
        name: '最高价',
        type: 'line',
        data: maxPrices,
        smooth: dates.length > 2,
        symbol: 'diamond',
        symbolSize: 6,
        lineStyle: { type: 'dashed', width: 1.5 },
        itemStyle: { color: '#EF4444' },
      },
    ],
  }
})
</script>
