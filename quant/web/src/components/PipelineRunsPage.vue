<script setup>
import { computed, onMounted, ref } from 'vue'
import { Loader2, Play, RefreshCw } from 'lucide-vue-next'
import { fetchPipelineRuns, runPipeline } from '../api/client'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import Input from './ui/Input.vue'

const PAGE_SIZE = 20

const RUN_STATUS = {
  ok: { label: '成功', variant: 'success' },
  failed: { label: '失败', variant: 'destructive' },
  skipped: { label: '跳过', variant: 'secondary' },
  running: { label: '运行中', variant: 'warning' },
}

const STAGE_LABELS = { ingest: '取数', indexes: '指数', evaluate: '求值', report: '日报' }
const TRIGGER_LABELS = { scheduled: '定时', manual: '手动', catchup: '补跑' }

const items = ref([])
const total = ref(0)
const cursor = ref(null)
const page = ref(1)
const loading = ref(false)
const error = ref('')

const runDate = ref(today())
const running = ref(false)
const runResult = ref(null)

function today() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchPipelineRuns({ page: page.value, pageSize: PAGE_SIZE })
    items.value = data.items
    total.value = data.total
    cursor.value = data.cursor
  } catch (err) {
    error.value = err.message
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function trigger(catchUp) {
  running.value = true
  error.value = ''
  runResult.value = null
  try {
    runResult.value = await runPipeline(runDate.value, catchUp)
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    running.value = false
  }
}

function goPage(delta) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  load()
}

function statusOf(status) {
  return RUN_STATUS[status] || { label: status, variant: 'secondary' }
}

function timeOf(value) {
  if (!value) return '—'
  return value.slice(11, 19)
}

function stageSummary(run) {
  return run.stages
    .map((stage) => `${STAGE_LABELS[stage.stage] || stage.stage} ${stage.elapsedMs}ms`)
    .join(' · ')
}

function stageVariant(status) {
  if (status === 'ok') return 'success'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">运行记录</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          收盘后自动跑「取数 → 求值 → 推送 → 日报」，这里能看到每次跑到了哪一步。
        </p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="load">
        <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" /> 刷新
      </Button>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <Card class="mb-4">
      <CardContent class="flex flex-wrap items-end gap-3 pt-6">
        <div>
          <label class="mb-1 block text-xs text-muted-foreground" for="run-date">交易日</label>
          <Input id="run-date" v-model="runDate" class="w-40" placeholder="YYYY-MM-DD" />
        </div>
        <Button :disabled="running" @click="trigger(false)">
          <Loader2 v-if="running" class="h-3.5 w-3.5 animate-spin" />
          <Play v-else class="h-3.5 w-3.5" />
          立即运行
        </Button>
        <Button variant="outline" :disabled="running" @click="trigger(true)">
          补跑缺口
        </Button>
        <p class="ml-auto text-xs text-muted-foreground">
          增量游标：<span class="font-mono">{{ cursor || '尚未成功运行' }}</span>
        </p>
      </CardContent>
    </Card>

    <p v-if="runResult?.run" class="mb-4 rounded-lg border bg-secondary px-3 py-2 text-sm">
      {{ runResult.run.tradeDate }} 运行
      <span class="font-medium">{{ statusOf(runResult.run.status).label }}</span>
      <span class="text-muted-foreground">（{{ stageSummary(runResult.run) }}）</span>
    </p>
    <p v-else-if="runResult?.runs" class="mb-4 rounded-lg border bg-secondary px-3 py-2 text-sm">
      补齐 {{ runResult.count }} 个交易日
    </p>

    <p v-if="!loading && items.length === 0" class="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
      还没有运行记录。收盘后会自动触发，也可以在上面手动运行一次。
    </p>

    <div v-else class="space-y-3">
      <Card v-for="run in items" :key="run.id">
        <CardContent class="pt-6">
          <div class="flex flex-wrap items-center gap-3">
            <span class="font-mono font-medium">{{ run.tradeDate }}</span>
            <Badge :variant="statusOf(run.status).variant">{{ statusOf(run.status).label }}</Badge>
            <Badge variant="outline">{{ TRIGGER_LABELS[run.triggerKind] || run.triggerKind }}</Badge>
            <span class="text-xs text-muted-foreground">
              {{ timeOf(run.startedAt) }}<span v-if="run.finishedAt"> – {{ timeOf(run.finishedAt) }}</span>
            </span>
            <span class="ml-auto text-xs text-muted-foreground">{{ stageSummary(run) }}</span>
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            <div
              v-for="stage in run.stages"
              :key="stage.stage"
              class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs"
            >
              <span class="font-medium">{{ STAGE_LABELS[stage.stage] || stage.stage }}</span>
              <Badge :variant="stageVariant(stage.status)">
                {{ statusOf(stage.status).label }}
              </Badge>
              <span class="text-muted-foreground">{{ stage.elapsedMs }}ms</span>
              <span v-if="stage.detail" class="text-muted-foreground">· {{ stage.detail }}</span>
            </div>
          </div>

          <p v-if="run.error" class="mt-2 text-xs text-destructive">失败原因：{{ run.error }}</p>
        </CardContent>
      </Card>
    </div>

    <div v-if="totalPages > 1" class="mt-4 flex items-center justify-end gap-2 text-sm">
      <Button variant="outline" size="sm" :disabled="page <= 1" @click="goPage(-1)">上一页</Button>
      <span class="text-xs text-muted-foreground">{{ page }} / {{ totalPages }}</span>
      <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="goPage(1)">下一页</Button>
    </div>
  </AppShell>
</template>
