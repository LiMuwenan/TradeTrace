<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, CheckCheck, RotateCcw } from 'lucide-vue-next'
import { fetchAlert, setAlertRead } from '../api/client'
import { metricText, num, pushStateText, ruleLabel } from '../lib/alertFormat'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import CardHeader from './ui/CardHeader.vue'
import CardTitle from './ui/CardTitle.vue'

const props = defineProps({
  id: { type: String, required: true },
})

const router = useRouter()
const data = ref(null)
const loading = ref(false)
const error = ref('')
const busy = ref(false)

const alert = computed(() => data.value?.alert || null)
const rule = computed(() => data.value?.rule || null)

const snapshot = computed(() => {
  const item = alert.value
  if (!item) return []
  return [
    { label: '指标', value: metricText(item) },
    { label: '触发值', value: num(item.value) },
    { label: '阈值', value: item.threshold === null || item.threshold === undefined ? '—' : num(item.threshold) },
    { label: '判定价（后复权）', value: num(item.price) },
    { label: '数据日期', value: item.tradeDate },
    { label: '推送状态', value: pushStateText(item) },
  ]
})

const ruleParams = computed(() => {
  const item = rule.value
  if (!item) return []
  return [
    { label: '规则类型', value: ruleLabel(item.type) },
    { label: '规则名称', value: item.name },
    { label: '时间窗', value: `${item.window}` },
    { label: '阈值', value: item.threshold === null ? '—' : num(item.threshold) },
    { label: '标的范围', value: item.scope === 'single' ? `指定单只（${item.scopeCode}）` : '全部自选' },
    { label: '启用状态', value: item.enabled ? '启用中' : '已停用' },
  ]
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchAlert(props.id)
  } catch (err) {
    error.value = err.message
    data.value = null
  } finally {
    loading.value = false
  }
}

async function toggleRead() {
  if (!alert.value) return
  busy.value = true
  try {
    await setAlertRead(alert.value.id, !alert.value.readAt)
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

watch(() => props.id, load, { immediate: true })
</script>

<template>
  <AppShell>
    <Button variant="ghost" size="sm" class="mb-4 -ml-2" @click="router.push('/alerts')">
      <ArrowLeft class="h-3.5 w-3.5" /> 返回预警列表
    </Button>

    <p v-if="error" class="rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>
    <div v-else-if="loading && !data" class="p-10 text-center text-sm text-muted-foreground">加载中…</div>

    <template v-else-if="alert">
      <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-xl font-semibold tracking-tight">{{ alert.code }}</h1>
            <span class="text-sm text-muted-foreground">{{ alert.name }}</span>
            <Badge variant="outline">{{ ruleLabel(alert.ruleType) }}</Badge>
            <Badge :variant="alert.readAt ? 'secondary' : 'warning'">{{ alert.readAt ? '已读' : '未读' }}</Badge>
          </div>
          <p class="mt-1 text-sm text-muted-foreground">{{ alert.ruleName }} · {{ alert.tradeDate }}</p>
        </div>
        <Button variant="outline" size="sm" :disabled="busy" @click="toggleRead">
          <CheckCheck v-if="!alert.readAt" class="h-3.5 w-3.5" />
          <RotateCcw v-else class="h-3.5 w-3.5" />
          {{ alert.readAt ? '标为未读' : '标为已读' }}
        </Button>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>触发快照</CardTitle>
          </CardHeader>
          <CardContent>
            <dl class="grid grid-cols-2 gap-x-4 gap-y-3">
              <div v-for="row in snapshot" :key="row.label">
                <dt class="text-xs text-muted-foreground">{{ row.label }}</dt>
                <dd class="mt-0.5 font-mono text-sm">{{ row.value }}</dd>
              </div>
            </dl>
            <p class="mt-4 text-xs text-muted-foreground">
              快照是触发当日留下的数值，不随规则后续修改而变化。
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>规则当前参数</CardTitle>
          </CardHeader>
          <CardContent>
            <dl v-if="rule" class="grid grid-cols-2 gap-x-4 gap-y-3">
              <div v-for="row in ruleParams" :key="row.label">
                <dt class="text-xs text-muted-foreground">{{ row.label }}</dt>
                <dd class="mt-0.5 text-sm">{{ row.value }}</dd>
              </div>
            </dl>
            <p v-else class="text-sm text-muted-foreground">该规则已被删除，仅保留触发时的快照值。</p>
            <p v-if="rule" class="mt-4 text-xs text-muted-foreground">
              这里是规则现在的设置；触发当时的时间窗与阈值见左侧「触发快照」。
            </p>
          </CardContent>
        </Card>
      </div>

      <p class="mt-4 rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground">
        {{ data.disclaimer }}
      </p>
    </template>
  </AppShell>
</template>
