<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronLeft, ChevronRight, FileText, RefreshCw } from 'lucide-vue-next'
import { fetchReports } from '../api/client'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'

const PAGE_SIZE = 20

const router = useRouter()
const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchReports({ page: page.value, pageSize: PAGE_SIZE })
    items.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err.message
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function goPage(delta) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  load()
}

function summaryText(summary) {
  if (!summary || !summary.total) return '暂无自选'
  const parts = [`涨 ${summary.up}`, `跌 ${summary.down}`, `平 ${summary.flat}`]
  if (summary.suspended) parts.push(`无数据 ${summary.suspended}`)
  return parts.join(' · ')
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">日报</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          共 {{ total }} 期。逐条预警负责「尽早知道」，日报负责「不漏」。
        </p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="load">
        <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" /> 刷新
      </Button>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <p v-if="!loading && items.length === 0" class="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
      还没有日报。收盘流水线跑完一个交易日后会在这里出现。
    </p>

    <div v-else class="space-y-3">
      <Card
        v-for="item in items"
        :key="item.tradeDate"
        class="cursor-pointer transition-colors hover:bg-accent"
        @click="router.push(`/reports/${item.tradeDate}`)"
      >
        <CardContent class="flex flex-wrap items-center gap-4 pt-6">
          <div class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-secondary">
            <FileText class="h-4 w-4 text-muted-foreground" />
          </div>

          <div class="min-w-[160px] flex-1">
            <div class="flex items-center gap-2">
              <span class="font-mono font-medium">{{ item.tradeDate }}</span>
              <Badge :variant="item.pushedAt ? 'success' : 'secondary'">
                {{ item.pushedAt ? '已投递' : '未投递' }}
              </Badge>
            </div>
            <p class="mt-1 text-sm text-muted-foreground">{{ summaryText(item.watchlistSummary) }}</p>
          </div>

          <div class="flex items-center gap-6 text-sm">
            <div class="text-right">
              <p class="text-xs text-muted-foreground">触发</p>
              <p class="mt-0.5 font-mono font-medium">{{ item.triggerCount }}</p>
            </div>
            <div class="text-right">
              <p class="text-xs text-muted-foreground">接近阈值</p>
              <p class="mt-0.5 font-mono font-medium">{{ item.nearMissCount }}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <div v-if="totalPages > 1" class="mt-4 flex items-center justify-end gap-2 text-sm">
      <Button variant="outline" size="sm" :disabled="page <= 1" @click="goPage(-1)">
        <ChevronLeft class="h-3.5 w-3.5" /> 上一页
      </Button>
      <span class="text-xs text-muted-foreground">{{ page }} / {{ totalPages }}</span>
      <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="goPage(1)">
        下一页 <ChevronRight class="h-3.5 w-3.5" />
      </Button>
    </div>
  </AppShell>
</template>
