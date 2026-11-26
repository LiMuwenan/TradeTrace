<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AccordionContent, AccordionHeader, AccordionItem, AccordionRoot, AccordionTrigger } from 'reka-ui'
import {
  Activity, BarChart3, Bell, ChevronDown, ChevronRight, CircleHelp, Database,
  ExternalLink, FileText, Home, LifeBuoy, ListFilter, Menu, PanelLeftClose, RefreshCw,
  Search, Settings2, Star,
} from 'lucide-vue-next'
import {
  addToWatchlist, fetchAlerts, fetchDataStatus, fetchHealth, fetchWatchlist,
  removeFromWatchlist, searchStocks,
} from '../api/client'
import { cn } from '../lib/utils'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import CardDescription from './ui/CardDescription.vue'
import CardHeader from './ui/CardHeader.vue'
import CardTitle from './ui/CardTitle.vue'
import Input from './ui/Input.vue'

const router = useRouter()

const activeNav = ref('控制台')
const sidebarCollapsed = ref(false)
const unreadAlerts = ref(0)

const health = ref(null)
const status = ref(null)
const error = ref('')
const loading = ref(false)

const watchlist = ref([])
const watchlistLoading = ref(false)
const watchlistError = ref('')
const keyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const searched = ref(false)
const namesAvailable = ref(true)

const healthRows = computed(() => [
  { label: '后端版本', value: health.value?.version },
  { label: '数据目录', value: health.value?.parquetDir, mono: true },
  { label: '原始数据目录', value: health.value?.rawDir, mono: true },
  { label: '时区', value: health.value?.timezone },
  { label: '服务器时间', value: health.value?.serverTime, mono: true },
])

const dateRange = computed(() => {
  const range = status.value?.dateRange
  if (!range?.start || !range?.end) return '—'
  return `${range.start} ~ ${range.end}`
})

const lastImport = computed(() => {
  const run = status.value?.lastImport
  if (!run) return null
  return {
    time: run.ranAt,
    status: run.status === 'ok' ? '成功' : '失败',
    ok: run.status === 'ok',
    rows: run.rows,
    days: (run.tradeDates || []).length,
    message: (run.warnings || []).join('；'),
  }
})

const missingDates = computed(() => status.value?.missingDates || [])

const stats = computed(() => [
  { label: '已归档行数', value: status.value ? status.value.totalRows.toLocaleString() : '—', icon: Database },
  { label: '自选标的', value: String(watchlist.value.length), icon: Star },
  { label: '日期范围', value: dateRange.value, icon: Activity, wide: true },
])

async function load() {
  loading.value = true
  error.value = ''
  const [healthResult, statusResult] = await Promise.allSettled([fetchHealth(), fetchDataStatus()])

  if (healthResult.status === 'fulfilled') {
    health.value = healthResult.value
  } else {
    health.value = null
    error.value = healthResult.reason.message
  }

  if (statusResult.status === 'fulfilled') {
    status.value = statusResult.value
  } else {
    status.value = null
    if (!error.value) error.value = statusResult.reason.message
  }

  loading.value = false
}

async function loadWatchlist() {
  watchlistLoading.value = true
  watchlistError.value = ''
  try {
    const data = await fetchWatchlist()
    watchlist.value = data.items
  } catch (err) {
    watchlist.value = []
    watchlistError.value = err.message
  } finally {
    watchlistLoading.value = false
  }
}

async function runSearch() {
  const query = keyword.value.trim()
  if (!query) {
    searchResults.value = []
    searched.value = false
    return
  }
  searching.value = true
  searched.value = false
  watchlistError.value = ''
  try {
    const data = await searchStocks(query)
    searchResults.value = data.items
    namesAvailable.value = data.namesAvailable
    searched.value = true
  } catch (err) {
    searchResults.value = []
    watchlistError.value = err.message
  } finally {
    searching.value = false
  }
}

async function addStock(code) {
  watchlistError.value = ''
  try {
    await addToWatchlist(code)
    searchResults.value = searchResults.value.filter((item) => item.code !== code)
    await loadWatchlist()
  } catch (err) {
    watchlistError.value = err.message
  }
}

async function removeStock(code) {
  watchlistError.value = ''
  try {
    await removeFromWatchlist(code)
    await loadWatchlist()
  } catch (err) {
    watchlistError.value = err.message
  }
}

function priceText(value) {
  return value == null ? '—' : value.toFixed(2)
}

function quoteText(item) {
  if (item.pctChg == null) return '—'
  return `${item.pctChg > 0 ? '+' : ''}${item.pctChg.toFixed(2)}%`
}

function quoteClass(item) {
  if (item.suspended || item.pctChg == null || item.pctChg === 0) return 'text-flat'
  return item.pctChg > 0 ? 'text-up' : 'text-down'
}

const navGroups = [
  {
    label: '工作区',
    items: [
      { label: '控制台', icon: Home, active: true },
    ],
  },
  {
    label: '数据',
    items: [
      { label: '服务状态', icon: Activity, target: 'health' },
      { label: '自选', icon: Star, target: 'watchlist' },
      { label: '数据状态', icon: Database, target: 'data-status' },
    ],
  },
  {
    label: '预警与规则',
    items: [
      { label: '规则', icon: ListFilter, to: '/rules' },
      { label: '预警列表', icon: Bell, to: '/alerts' },
      { label: '日报', icon: FileText, to: '/reports' },
      { label: '通知设置', icon: Settings2, to: '/settings/notification' },
    ],
  },
  {
    label: '资源',
    items: [
      { label: '返回首页', icon: ExternalLink, leave: true },
    ],
  },
]

function goTo(target) {
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadUnread() {
  try {
    const data = await fetchAlerts({ pageSize: 1, read: false })
    unreadAlerts.value = data.unreadCount
  } catch {
    unreadAlerts.value = 0
  }
}

onMounted(() => {
  load()
  loadWatchlist()
  loadUnread()
})
</script>

<template>
  <div class="min-h-screen bg-secondary/40">
    <aside
      :class="cn(
        'fixed inset-y-0 left-0 z-30 flex flex-col border-r bg-background transition-all duration-200',
        sidebarCollapsed ? 'w-[68px]' : 'w-[228px]'
      )"
    >
      <div class="flex h-14 items-center gap-2 border-b px-4">
        <span class="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">Q</span>
        <div v-if="!sidebarCollapsed" class="leading-tight">
          <p class="text-sm font-semibold">Quant Platform</p>
          <p class="text-[11px] text-muted-foreground">A 股数据分析</p>
        </div>
      </div>

      <div class="px-3 py-3">
        <div v-if="!sidebarCollapsed" class="flex items-center gap-2 rounded-lg border bg-background px-2.5 py-2 text-xs text-muted-foreground shadow-sm">
          <Search class="h-3.5 w-3.5" />
          <span class="flex-1">搜索</span>
          <kbd class="rounded border bg-secondary px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
        </div>
        <div v-else class="grid h-9 place-items-center">
          <Search class="h-4 w-4 text-muted-foreground" />
        </div>
      </div>

      <nav class="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        <div v-for="group in navGroups" :key="group.label">
          <p v-if="!sidebarCollapsed" class="mb-1.5 px-2 text-[11px] font-medium text-muted-foreground">{{ group.label }}</p>
          <button
            v-for="item in group.items"
            :key="item.label"
            :title="item.label"
            class="mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
            :class="[
              item.active && activeNav === item.label ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground/80',
              sidebarCollapsed ? 'justify-center' : ''
            ]"
            @click="item.leave ? router.push('/') : (item.to ? router.push(item.to) : (item.target ? goTo(item.target) : (activeNav = item.label)))"
          >
            <component :is="item.icon" class="h-4 w-4 shrink-0" />
            <span v-if="!sidebarCollapsed" class="flex-1 truncate">{{ item.label }}</span>
            <span
              v-if="item.to === '/alerts' && unreadAlerts && !sidebarCollapsed"
              class="rounded-full bg-warning-soft px-1.5 text-[11px] font-medium text-warning"
            >{{ unreadAlerts }}</span>
            <ChevronRight v-if="!sidebarCollapsed && item.leave" class="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        </div>
      </nav>

      <div class="border-t p-3">
        <button
          class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          :class="sidebarCollapsed ? 'justify-center' : ''"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <PanelLeftClose class="h-4 w-4" />
          <span v-if="!sidebarCollapsed">收起侧栏</span>
        </button>
      </div>
    </aside>

    <div :class="cn('transition-all duration-200', sidebarCollapsed ? 'pl-[68px]' : 'pl-[228px]')">
      <header class="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/90 px-6 backdrop-blur">
        <div class="flex items-center gap-2 text-sm">
          <Menu class="h-4 w-4 text-muted-foreground md:hidden" />
          <span class="text-muted-foreground">工作区</span>
          <ChevronRight class="h-3.5 w-3.5 text-muted-foreground" />
          <span class="font-medium">控制台</span>
        </div>
        <div class="flex items-center gap-3">
          <div class="hidden items-center gap-2 rounded-lg border bg-background px-3 py-1.5 text-xs text-muted-foreground shadow-sm sm:flex">
            <Search class="h-3.5 w-3.5" />
            <span>搜索</span>
            <kbd class="rounded border bg-secondary px-1.5 py-0.5 font-mono text-[10px]">⌘ K</kbd>
          </div>
          <button class="hidden items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground sm:flex">
            简体中文 <ChevronDown class="h-3 w-3" />
          </button>
          <button class="grid h-8 w-8 place-items-center rounded-lg border text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground" title="帮助">
            <CircleHelp class="h-4 w-4" />
          </button>
          <span class="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">Q</span>
        </div>
      </header>

      <main class="mx-auto max-w-[1100px] px-6 py-8">
        <div class="mb-7 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">我的工作台</h1>
            <p class="mt-1 text-sm text-muted-foreground">只读行情，不接交易 · 数据更新后即可查看</p>
          </div>
          <Button variant="outline" size="sm" :disabled="loading" @click="load">
            <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" /> 刷新
          </Button>
        </div>

        <div class="mb-8 grid gap-3 sm:grid-cols-3">
          <Card v-for="stat in stats" :key="stat.label" :class="stat.wide ? 'sm:col-span-1' : ''">
            <CardContent class="flex items-center gap-4 p-5">
              <div class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent text-accent-foreground">
                <component :is="stat.icon" class="h-4 w-4" />
              </div>
              <div class="min-w-0">
                <p class="text-xs text-muted-foreground">{{ stat.label }}</p>
                <p class="mt-0.5 truncate font-mono text-lg font-semibold">{{ stat.value }}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <p v-if="error" class="mb-5 rounded-lg border border-destructive bg-background px-4 py-3 text-sm text-destructive">{{ error }}</p>

        <section id="health" class="mb-6 scroll-mt-20">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-base font-semibold">服务状态</h2>
            <Badge :variant="health ? 'success' : 'outline'">
              <span class="mr-1.5 h-1.5 w-1.5 rounded-full" :class="health ? 'bg-down' : 'bg-flat'" />
              {{ loading ? '检测中…' : health ? '在线' : '离线' }}
            </Badge>
          </div>
          <Card>
            <CardContent class="divide-y p-0">
              <div v-for="row in healthRows" :key="row.label" class="flex flex-wrap gap-4 px-5 py-3">
                <span class="w-28 shrink-0 text-sm text-muted-foreground">{{ row.label }}</span>
                <span class="flex-1 break-all text-sm" :class="row.mono ? 'font-mono text-xs' : ''">{{ row.value ?? '—' }}</span>
              </div>
            </CardContent>
          </Card>
        </section>

        <section id="watchlist" class="mb-6 scroll-mt-20">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-base font-semibold">自选</h2>
            <span class="text-xs text-muted-foreground">{{ watchlist.length }} 个标的</span>
          </div>
          <Card>
            <CardContent class="p-5">
              <form class="flex gap-2" @submit.prevent="runSearch">
                <Input v-model="keyword" type="search" placeholder="输入代码或名称，如 600519 / 茅台" aria-label="搜索标的" />
                <Button type="submit" :disabled="searching || !keyword.trim()">{{ searching ? '搜索中…' : '搜索' }}</Button>
              </form>

              <p v-if="!namesAvailable" class="mt-3 text-xs text-warning">名称字典暂不可用，只能按代码搜索。</p>

              <ul v-if="searchResults.length" class="mt-3 divide-y overflow-hidden rounded-lg border">
                <li v-for="item in searchResults" :key="item.code" class="flex items-center gap-3 px-3 py-2.5">
                  <span class="w-24 font-mono text-xs text-muted-foreground">{{ item.code }}</span>
                  <span class="flex-1 text-sm">{{ item.name || '—' }}</span>
                  <Button variant="outline" size="sm" @click="addStock(item.code)">加入</Button>
                </li>
              </ul>
              <p v-else-if="searched && !searching" class="mt-3 text-sm text-muted-foreground">没有匹配的标的。</p>

              <div v-if="watchlist.length" class="mt-5 overflow-hidden rounded-lg border">
                <div class="grid grid-cols-[110px_1fr_110px_100px_100px_64px] gap-2 border-b bg-secondary/50 px-3 py-2.5 text-xs text-muted-foreground">
                  <span>代码</span><span>名称</span><span>最新交易日</span>
                  <span class="text-right">收盘价</span><span class="text-right">涨跌幅</span><span></span>
                </div>
                <div
                  v-for="item in watchlist"
                  :key="item.code"
                  class="grid grid-cols-[110px_1fr_110px_100px_100px_64px] items-center gap-2 border-b px-3 py-2.5 text-sm last:border-b-0"
                >
                  <button class="text-left font-mono text-xs text-primary hover:underline" @click="router.push(`/stocks/${item.code}`)">{{ item.code }}</button>
                  <button class="truncate text-left hover:underline" @click="router.push(`/stocks/${item.code}`)">{{ item.name || '—' }}</button>
                  <span class="font-mono text-xs text-muted-foreground">{{ item.date || '—' }}</span>
                  <span class="text-right font-mono">{{ priceText(item.close) }}</span>
                  <span class="text-right font-mono font-medium" :class="quoteClass(item)">
                    {{ item.suspended ? '停牌' : quoteText(item) }}
                  </span>
                  <Button variant="ghost" size="sm" class="h-7 px-2 text-xs text-muted-foreground hover:text-destructive" @click="removeStock(item.code)">移除</Button>
                </div>
              </div>
              <p v-else-if="!watchlistLoading" class="mt-4 rounded-lg bg-secondary/50 px-4 py-3 text-sm text-muted-foreground">
                还没有自选标的。用上方搜索按代码或名称添加，例如 <code class="font-mono">600519</code> 或 <code class="font-mono">茅台</code>。
              </p>

              <p v-if="watchlistError" class="mt-3 rounded-lg border border-destructive bg-background px-4 py-3 text-sm text-destructive">{{ watchlistError }}</p>
            </CardContent>
          </Card>
        </section>

        <section id="data-status" class="mb-6 scroll-mt-20">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-base font-semibold">数据状态</h2>
            <span class="text-xs text-muted-foreground">最近导入：{{ lastImport?.time || '—' }}</span>
          </div>
          <Card>
            <CardContent class="divide-y p-0">
              <div class="flex flex-wrap gap-4 px-5 py-3">
                <span class="w-28 shrink-0 text-sm text-muted-foreground">总行数</span>
                <span class="flex-1 font-mono text-sm">{{ status ? status.totalRows.toLocaleString() : '—' }}</span>
              </div>
              <div class="flex flex-wrap gap-4 px-5 py-3">
                <span class="w-28 shrink-0 text-sm text-muted-foreground">日期范围</span>
                <span class="flex-1 font-mono text-sm">{{ dateRange }}</span>
              </div>
              <div class="flex flex-wrap gap-4 px-5 py-3">
                <span class="w-28 shrink-0 text-sm text-muted-foreground">最近导入</span>
                <span class="flex-1 text-sm">
                  <template v-if="lastImport">
                    <span :class="lastImport.ok ? 'text-down' : 'text-up'">{{ lastImport.status }}</span>
                    · {{ lastImport.rows }} 行 · {{ lastImport.days }} 个交易日
                    <span class="ml-1 font-mono text-xs text-muted-foreground">{{ lastImport.time }}</span>
                  </template>
                  <span v-else class="text-muted-foreground">尚无导入记录</span>
                </span>
              </div>
              <div v-if="lastImport?.message" class="px-5 py-3 text-sm text-muted-foreground">{{ lastImport.message }}</div>
              <div class="flex flex-wrap gap-4 px-5 py-3">
                <span class="w-28 shrink-0 text-sm text-muted-foreground">缺失交易日</span>
                <span class="flex flex-1 flex-wrap items-center gap-1.5">
                  <template v-if="missingDates.length === 0"><span class="text-sm text-muted-foreground">无</span></template>
                  <template v-else>
                    <Badge v-for="day in missingDates.slice(0, 12)" :key="day" variant="secondary" class="font-mono">{{ day }}</Badge>
                    <span v-if="missingDates.length > 12" class="text-xs text-muted-foreground">还有 {{ missingDates.length - 12 }} 个</span>
                  </template>
                </span>
              </div>
            </CardContent>
          </Card>
          <p v-if="status && status.totalRows === 0" class="mt-3 rounded-lg bg-secondary/50 px-4 py-3 text-sm text-muted-foreground">
            尚无行情数据。把历史 CSV 按 <code class="font-mono">daily/YYYY-MM-DD.csv</code>、
            <code class="font-mono">factors/YYYY-MM-DD.csv</code> 放进原始数据目录后，运行
            <code class="font-mono">python -m app.import_history</code>。
          </p>
        </section>

        <Card class="mb-6">
          <CardHeader class="pb-3">
            <CardTitle>说明与帮助</CardTitle>
            <CardDescription>关于数据口径与平台边界</CardDescription>
          </CardHeader>
          <CardContent class="pt-0">
            <AccordionRoot type="single" collapsible>
              <AccordionItem value="scope" class="border-t">
                <AccordionHeader>
                  <AccordionTrigger class="flex w-full items-center justify-between py-4 text-left text-sm font-medium hover:no-underline">
                    平台边界 <ChevronDown class="h-4 w-4 shrink-0 text-muted-foreground transition-transform" />
                  </AccordionTrigger>
                </AccordionHeader>
                <AccordionContent class="pb-4 text-sm leading-6 text-muted-foreground">
                  本平台只读行情，不接交易，不输出投资建议。交易记录、持仓与收益统计属于另一个项目。
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="price" class="border-t">
                <AccordionHeader>
                  <AccordionTrigger class="flex w-full items-center justify-between py-4 text-left text-sm font-medium hover:no-underline">
                    复权口径 <ChevronDown class="h-4 w-4 shrink-0 text-muted-foreground transition-transform" />
                  </AccordionTrigger>
                </AccordionHeader>
                <AccordionContent class="pb-4 text-sm leading-6 text-muted-foreground">
                  存储只存不复权价与后复权因子；跨日比较一律用后复权价，避免除权当日跳空造成虚假信号。
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="alert" class="border-t">
                <AccordionHeader>
                  <AccordionTrigger class="flex w-full items-center justify-between py-4 text-left text-sm font-medium hover:no-underline">
                    预警与日报 <ChevronDown class="h-4 w-4 shrink-0 text-muted-foreground transition-transform" />
                  </AccordionTrigger>
                </AccordionHeader>
                <AccordionContent class="pb-4 text-sm leading-6 text-muted-foreground">
                  触发是从「不满足」变为「满足」的那一刻；连续满足只算一次触发。日报另外收录接近阈值的条目。
                </AccordionContent>
              </AccordionItem>
            </AccordionRoot>
          </CardContent>
        </Card>

        <footer class="flex flex-wrap items-center justify-between gap-3 border-t pt-6 text-xs text-muted-foreground">
          <span>Quant Platform · 本平台仅提供数据分析，不构成投资建议</span>
          <div class="flex items-center gap-4">
            <button class="flex items-center gap-1 hover:text-foreground" @click="router.push('/')"><Home class="h-3.5 w-3.5" /> 首页</button>
            <button class="flex items-center gap-1 hover:text-foreground"><LifeBuoy class="h-3.5 w-3.5" /> 帮助</button>
            <button class="flex items-center gap-1 hover:text-foreground" @click="router.push('/settings/notification')"><Settings2 class="h-3.5 w-3.5" /> 设置</button>
          </div>
        </footer>
      </main>
    </div>
  </div>
</template>
