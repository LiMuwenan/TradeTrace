<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BellRing, CheckCheck, ChevronLeft, ChevronRight, RefreshCw, Search } from 'lucide-vue-next'
import { fetchAlerts, markAllAlertsRead, setAlertRead } from '../api/client'
import { RULE_TYPE_LABELS, metricText, num, pushStateText, ruleLabel } from '../lib/alertFormat'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'

const router = useRouter()

const PAGE_SIZE = 20

const items = ref([])
const total = ref(0)
const unread = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const busyId = ref(null)

const filters = reactive({ read: '', ruleType: '', code: '' })

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasFilter = computed(() => Boolean(filters.read || filters.ruleType || filters.code.trim()))

function readParam() {
  if (filters.read === 'true') return true
  if (filters.read === 'false') return false
  return undefined
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAlerts({
      read: readParam(),
      code: filters.code.trim() || undefined,
      ruleType: filters.ruleType || undefined,
      page: page.value,
      pageSize: PAGE_SIZE,
    })
    items.value = data.items
    total.value = data.total
    unread.value = data.unreadCount
  } catch (err) {
    error.value = err.message
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.read = ''
  filters.ruleType = ''
  filters.code = ''
  search()
}

function goPage(delta) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  load()
}

async function toggleRead(item) {
  busyId.value = item.id
  try {
    await setAlertRead(item.id, !item.readAt)
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busyId.value = null
  }
}

async function markAll() {
  busyId.value = -1
  try {
    await markAllAlertsRead()
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <AppShell :unread="unread">
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">预警</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          共 {{ total }} 条<span v-if="unread">，其中 <span class="font-medium text-warning">{{ unread }} 条未读</span></span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" /> 刷新
        </Button>
        <Button size="sm" :disabled="busyId !== null || unread === 0" @click="markAll">
          <CheckCheck class="h-3.5 w-3.5" /> 全部标为已读
        </Button>
      </div>
    </div>

    <Card class="mb-4">
      <CardContent class="flex flex-wrap items-center gap-3 pt-6">
        <div class="flex items-center gap-1.5">
          <label class="text-xs text-muted-foreground" for="filter-read">状态</label>
          <select
            id="filter-read"
            v-model="filters.read"
            class="h-9 rounded-lg border border-input bg-background px-2 text-sm"
            @change="search"
          >
            <option value="">全部</option>
            <option value="false">未读</option>
            <option value="true">已读</option>
          </select>
        </div>

        <div class="flex items-center gap-1.5">
          <label class="text-xs text-muted-foreground" for="filter-type">规则</label>
          <select
            id="filter-type"
            v-model="filters.ruleType"
            class="h-9 rounded-lg border border-input bg-background px-2 text-sm"
            @change="search"
          >
            <option value="">全部</option>
            <option v-for="(label, type) in RULE_TYPE_LABELS" :key="type" :value="type">{{ label }}</option>
          </select>
        </div>

        <div class="flex items-center gap-1.5">
          <label class="text-xs text-muted-foreground" for="filter-code">标的</label>
          <input
            id="filter-code"
            v-model="filters.code"
            class="h-9 w-36 rounded-lg border border-input bg-background px-2 text-sm"
            placeholder="sh.600000"
            @keyup.enter="search"
          />
        </div>

        <Button variant="outline" size="sm" @click="search">
          <Search class="h-3.5 w-3.5" /> 查询
        </Button>
        <Button v-if="hasFilter" variant="ghost" size="sm" @click="reset">重置</Button>
      </CardContent>
    </Card>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <Card>
      <div v-if="loading && items.length === 0" class="p-10 text-center text-sm text-muted-foreground">加载中…</div>

      <div v-else-if="items.length === 0" class="flex flex-col items-center gap-2 p-12 text-center">
        <BellRing class="h-6 w-6 text-muted-foreground" />
        <p class="text-sm font-medium">没有符合条件的预警</p>
        <p class="text-xs text-muted-foreground">
          {{ hasFilter ? '试试放宽筛选条件' : '规则触发后才会产生预警；可在控制台手动求值一次' }}
        </p>
      </div>

      <ul v-else class="divide-y">
        <li v-for="item in items" :key="item.id">
          <div class="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-accent">
            <span
              class="mt-1.5 h-2 w-2 shrink-0 rounded-full"
              :class="item.readAt ? 'bg-border' : 'bg-warning-soft0'"
              :title="item.readAt ? '已读' : '未读'"
            />

            <button class="min-w-0 flex-1 text-left" @click="router.push(`/alerts/${item.id}`)">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium">{{ item.code }}</span>
                <span class="text-sm text-muted-foreground">{{ item.name }}</span>
                <Badge variant="outline">{{ ruleLabel(item.ruleType) }}</Badge>
                <span class="text-sm">{{ item.ruleName }}</span>
              </div>
              <div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{{ metricText(item) }}</span>
                <span>判定价 {{ num(item.price) }}</span>
                <span>{{ item.tradeDate }}</span>
                <span :class="item.pushedAt ? 'text-success' : 'text-warning'">{{ pushStateText(item) }}</span>
              </div>
            </button>

            <Button
              variant="ghost"
              size="sm"
              class="shrink-0"
              :disabled="busyId === item.id"
              @click="toggleRead(item)"
            >
              {{ item.readAt ? '标为未读' : '标为已读' }}
            </Button>
          </div>
        </li>
      </ul>

      <div v-if="total > PAGE_SIZE" class="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" :disabled="page <= 1 || loading" @click="goPage(-1)">
            <ChevronLeft class="h-3.5 w-3.5" /> 上一页
          </Button>
          <Button variant="outline" size="sm" :disabled="page >= totalPages || loading" @click="goPage(1)">
            下一页 <ChevronRight class="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </Card>
  </AppShell>
</template>
