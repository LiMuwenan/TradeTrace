<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'
import { fetchReport } from '../api/client'
import { metricText } from '../lib/alertFormat'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import CardHeader from './ui/CardHeader.vue'
import CardTitle from './ui/CardTitle.vue'

const route = useRoute()
const router = useRouter()

const data = ref(null)
const loading = ref(false)
const error = ref('')

const report = computed(() => data.value?.report || null)
const summary = computed(() => report.value?.watchlistSummary || null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchReport(String(route.params.date))
  } catch (err) {
    error.value = err.message
    data.value = null
  } finally {
    loading.value = false
  }
}

function summaryText(value) {
  if (!value || !value.total) return '暂无自选'
  const parts = [`涨 ${value.up}`, `跌 ${value.down}`, `平 ${value.flat}`]
  if (value.suspended) parts.push(`无数据 ${value.suspended}`)
  return parts.join(' · ')
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="mb-5">
      <Button variant="ghost" size="sm" class="-ml-2 mb-2 text-muted-foreground" @click="router.push('/reports')">
        <ArrowLeft class="h-3.5 w-3.5" /> 返回日报列表
      </Button>

      <div v-if="report" class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-xl font-semibold tracking-tight">{{ report.tradeDate }} 收盘日报</h1>
          <p class="mt-1 text-sm text-muted-foreground">
            数据日期 {{ report.dataDate }} · 自选 {{ summaryText(summary) }}
          </p>
        </div>
        <Badge v-if="data" :variant="data.pushedAt ? 'success' : 'secondary'">
          {{ data.pushedAt ? `已投递（${data.pushChannel || '未知通道'}）` : '未投递' }}
        </Badge>
      </div>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <p v-if="loading" class="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 class="h-4 w-4 animate-spin" /> 加载中
    </p>

    <div v-if="report" class="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>触发清单（{{ report.triggers.length }}）</CardTitle>
        </CardHeader>
        <CardContent>
          <ul v-if="report.triggers.length" class="divide-y">
            <li v-for="item in report.triggers" :key="`${item.code}-${item.ruleId}`" class="flex flex-wrap items-center gap-3 py-2.5 text-sm first:pt-0 last:pb-0">
              <span class="w-24 font-mono text-xs text-muted-foreground">{{ item.code }}</span>
              <span class="min-w-[90px] flex-1 truncate">{{ item.name || '—' }}</span>
              <span class="min-w-[120px] text-muted-foreground">{{ item.ruleName }}</span>
              <span class="font-mono">{{ metricText(item) }}</span>
            </li>
          </ul>
          <p v-else class="text-sm text-muted-foreground">今日无触发。</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>接近阈值（{{ report.nearMisses.length }}）</CardTitle>
        </CardHeader>
        <CardContent>
          <ul v-if="report.nearMisses.length" class="divide-y">
            <li v-for="item in report.nearMisses" :key="`${item.code}-${item.ruleId}`" class="flex flex-wrap items-center gap-3 py-2.5 text-sm first:pt-0 last:pb-0">
              <span class="w-24 font-mono text-xs text-muted-foreground">{{ item.code }}</span>
              <span class="min-w-[90px] flex-1 truncate">{{ item.name || '—' }}</span>
              <span class="min-w-[120px] text-muted-foreground">{{ item.ruleName }}</span>
              <span class="font-mono">{{ metricText(item) }}</span>
            </li>
          </ul>
          <p v-else class="text-sm text-muted-foreground">没有接近阈值的标的。</p>
        </CardContent>
      </Card>

      <p class="text-xs text-muted-foreground">{{ data?.disclaimer || '本内容仅为数据分析，不构成投资建议' }}</p>
    </div>
  </AppShell>
</template>
