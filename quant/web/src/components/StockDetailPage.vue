<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { fetchStockDetail } from '../api/client'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'

echarts.use([CandlestickChart, LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

const MA_WINDOWS = [5, 10, 20, 60]
const RANGES = [
  { key: '3m', label: '3 个月' },
  { key: '1y', label: '1 年' },
  { key: 'all', label: '全部' },
]
// 默认后复权：与规则求值同口径；不复权用于和行情软件对价
const ADJUSTS = [
  { key: 'back', label: '后复权' },
  { key: 'raw', label: '不复权' },
]

const route = useRoute()
const router = useRouter()

const code = computed(() => String(route.params.code || ''))
const range = ref('1y')
const adjust = ref('back')
const activeMa = ref([...MA_WINDOWS])
const data = ref(null)
const loading = ref(false)
const error = ref('')
const chartEl = ref(null)

let chart = null

/** 图表是 canvas 绘制，不认 CSS 变量，只能把 token 的值读出来再拼成颜色。 */
function cssColor(name, fallback) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return raw ? `hsl(${raw.replace(/\s+/g, ', ')})` : fallback
}

function render() {
  if (!chartEl.value || !data.value) return
  if (!chart) chart = echarts.init(chartEl.value)

  const detail = data.value
  const dates = detail.items.map((item) => item.date)
  const up = cssColor('--up', '#d64545')
  const down = cssColor('--down', '#22a06b')
  const maColors = {
    5: cssColor('--primary', '#3b5bdb'),
    10: cssColor('--warning', '#c77a10'),
    20: cssColor('--success', '#1f8a5b'),
    60: cssColor('--muted-foreground', '#6b7280'),
  }

  const series = [
    {
      name: 'K 线',
      type: 'candlestick',
      data: detail.items.map((item) => [item.open, item.close, item.low, item.high]),
      itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down },
    },
    ...activeMa.value.map((window) => ({
      name: `MA${window}`,
      type: 'line',
      // 均线数组与 K 线等长，前 window-1 个点是 null（不足窗口），不能连成一条线
      data: detail.ma[String(window)],
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.2 },
      itemStyle: { color: maColors[window] },
      emphasis: { disabled: true },
    })),
  ]

  chart.setOption(
    {
      animation: false,
      grid: { left: 8, right: 12, top: 28, bottom: 56, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        valueFormatter: (value) => (value === null || value === undefined ? '—' : Number(value).toFixed(2)),
      },
      legend: { top: 0, right: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: cssColor('--border', '#e5e7eb') } },
        axisLabel: { fontSize: 10, hideOverlap: true },
      },
      yAxis: {
        scale: true,
        splitLine: { lineStyle: { color: cssColor('--border', '#e5e7eb'), type: 'dashed' } },
        axisLabel: { fontSize: 10, formatter: (value) => Number(value).toFixed(2) },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', height: 18, bottom: 8, borderColor: 'transparent' },
      ],
      series,
    },
    true
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchStockDetail(code.value, range.value, adjust.value)
    await nextTick()
    render()
  } catch (err) {
    error.value = err.message
    data.value = null
  } finally {
    loading.value = false
  }
}

function toggleMa(window) {
  const index = activeMa.value.indexOf(window)
  if (index >= 0) {
    // 至少留一条，全关掉图上看不出趋势
    if (activeMa.value.length === 1) return
    activeMa.value.splice(index, 1)
  } else {
    activeMa.value.push(window)
    activeMa.value.sort((a, b) => a - b)
  }
  render()
}

function price(value) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(2)
}

const changeText = computed(() => {
  const value = data.value?.latest?.pctChg
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(2)}%`
})

const changeClass = computed(() => {
  const value = data.value?.latest?.pctChg
  if (!value) return 'text-flat'
  return value > 0 ? 'text-up' : 'text-down'
})

/** 顶部主价跟随所选口径，另一个口径降为对照小字——两个数都摆出来，用户不会以为哪里算错了。 */
const isIndex = computed(() => data.value?.kind === 'index')
const adjustLabel = computed(() => (data.value?.adjust === 'raw' ? '不复权价' : '后复权价'))
const otherLabel = computed(() => (data.value?.adjust === 'raw' ? '后复权' : '不复权'))
const otherPrice = computed(() => {
  const latest = data.value?.latest
  if (!latest) return null
  return data.value.adjust === 'raw' ? latest.adjClose : latest.rawClose
})

function onResize() {
  chart?.resize()
}

watch([range, adjust, code], load)

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <AppShell>
    <div class="mb-5">
      <Button variant="ghost" size="sm" class="-ml-2 mb-2 text-muted-foreground" @click="router.back()">
        <ArrowLeft class="h-3.5 w-3.5" /> 返回
      </Button>

      <div v-if="data" class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-xl font-semibold tracking-tight">{{ data.name || data.code }}</h1>
            <span class="font-mono text-xs text-muted-foreground">{{ data.code }}</span>
            <Badge v-if="isIndex" variant="secondary">指数</Badge>
            <Badge v-if="data.inWatchlist" variant="secondary">自选</Badge>
          </div>
          <div class="mt-2 flex items-baseline gap-3">
            <span class="font-mono text-2xl font-semibold">{{ price(data.latest.close) }}</span>
            <span class="font-mono text-sm font-medium" :class="changeClass">{{ changeText }}</span>
            <span class="text-xs text-muted-foreground">最近交易日 {{ data.latest.date }}</span>
          </div>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ isIndex ? '指数点位' : adjustLabel
            }}<span v-if="!isIndex && otherPrice !== null"> · {{ otherLabel }} {{ price(otherPrice) }}</span>
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <div v-if="!isIndex" class="flex items-center gap-1 rounded-lg border p-0.5">
            <button
              v-for="item in ADJUSTS"
              :key="item.key"
              class="rounded-md px-3 py-1.5 text-sm transition-colors"
              :class="adjust === item.key ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:text-foreground'"
              @click="adjust = item.key"
            >
              {{ item.label }}
            </button>
          </div>

          <div class="flex items-center gap-1 rounded-lg border p-0.5">
            <button
              v-for="item in RANGES"
              :key="item.key"
              class="rounded-md px-3 py-1.5 text-sm transition-colors"
              :class="range === item.key ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:text-foreground'"
              @click="range = item.key"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <Card>
      <CardContent class="pt-6">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <span class="mr-1 text-xs text-muted-foreground">均线</span>
          <button
            v-for="window in MA_WINDOWS"
            :key="window"
            class="rounded-full border px-2.5 py-0.5 text-xs transition-colors"
            :class="activeMa.includes(window)
              ? 'border-transparent bg-accent font-medium text-accent-foreground'
              : 'border-border text-muted-foreground hover:text-foreground'"
            @click="toggleMa(window)"
          >
            MA{{ window }}
          </button>
          <span v-if="loading" class="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 class="h-3.5 w-3.5 animate-spin" /> 加载中
          </span>
        </div>

        <div v-show="data && data.items.length" ref="chartEl" class="h-[460px] w-full" />

        <p v-if="!loading && data && !data.items.length" class="py-16 text-center text-sm text-muted-foreground">
          该标的暂无行情数据。
        </p>
      </CardContent>
    </Card>

    <div v-if="data" class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
      <span>{{ data.adjustNote }}</span>
      <span>仅为数据分析，不构成投资建议</span>
    </div>
  </AppShell>
</template>
