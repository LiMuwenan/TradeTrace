<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Loader2, Pencil, Plus, Power, RefreshCw, X } from 'lucide-vue-next'
import { createRule, fetchRules, setRuleEnabled, updateRule } from '../api/client'
import { RULE_TYPE_LABELS } from '../lib/alertFormat'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import CardDescription from './ui/CardDescription.vue'
import CardHeader from './ui/CardHeader.vue'
import CardTitle from './ui/CardTitle.vue'
import Input from './ui/Input.vue'

const THRESHOLD_TYPES = ['oversold', 'volume_surge', 'volume_shrink']
const DEFAULT_WINDOW = {
  breakout: 60,
  oversold: 60,
  volume_surge: 5,
  volume_shrink: 5,
  ma_cross: 20,
}

const items = ref([])
const loading = ref(false)
const error = ref('')

const showForm = ref(false)
const editing = ref(null)
const saving = ref(false)
const formError = ref('')
const busyId = ref(null)
const busyText = ref('')

const form = reactive(blank())

function blank() {
  return { type: 'ma_cross', name: '', scope: 'watchlist', scopeCode: '', window: 20, threshold: null }
}

const needsThreshold = computed(() => THRESHOLD_TYPES.includes(form.type))
const isEditing = computed(() => editing.value !== null)

function thresholdHint(type) {
  if (type === 'oversold') return '回落百分比，例如 20 表示较高点回落 20%'
  if (type === 'volume_surge') return '量比下限，例如 1.5 表示放量到 5 日均量的 1.5 倍'
  if (type === 'volume_shrink') return '量比上限，例如 0.6 表示缩量到 5 日均量的 0.6 倍'
  return ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchRules()
    items.value = data.items
  } catch (err) {
    error.value = err.message
    items.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, blank())
  editing.value = null
  formError.value = ''
  showForm.value = true
}

function openEdit(rule) {
  Object.assign(form, {
    type: rule.type,
    name: rule.name,
    scope: rule.scope,
    scopeCode: rule.scopeCode || '',
    window: rule.window,
    threshold: rule.threshold,
  })
  editing.value = rule.id
  formError.value = ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editing.value = null
  formError.value = ''
}

function onTypeChange() {
  // 换类型时把时间窗与阈值换成该类型的常规起点，避免留着上一个类型的残留值
  if (!isEditing.value) {
    form.window = DEFAULT_WINDOW[form.type] ?? 20
    form.threshold = null
  }
}

function validate() {
  if (!form.name.trim()) return '请填写规则名称'
  if (!Number.isInteger(Number(form.window)) || Number(form.window) < 2) return '时间窗不得小于 2'
  if (needsThreshold.value) {
    const value = Number(form.threshold)
    if (form.threshold === null || form.threshold === '' || Number.isNaN(value)) return '请填写阈值'
    if (form.type === 'oversold' && (value <= 0 || value > 100)) return '超跌阈值应在 (0, 100] 之间'
    if (form.type !== 'oversold' && value <= 0) return '量比阈值必须大于 0'
  }
  if (form.scope === 'single' && !form.scopeCode.trim()) return '选择「指定单只」时必须填写标的代码'
  return ''
}

async function submit() {
  formError.value = validate()
  if (formError.value) return

  saving.value = true
  try {
    const window = Number(form.window)
    const threshold = needsThreshold.value ? Number(form.threshold) : null
    if (isEditing.value) {
      await updateRule(editing.value, { name: form.name.trim(), window, threshold })
    } else {
      // 新建会先做静默回放，按钮上的提示要让用户知道这一下会等几秒
      busyText.value = '正在按历史数据计算触发状态，请稍候…'
      await createRule({
        type: form.type,
        name: form.name.trim(),
        scope: form.scope,
        scopeCode: form.scope === 'single' ? form.scopeCode.trim() : null,
        window,
        threshold,
      })
    }
    closeForm()
    await load()
  } catch (err) {
    formError.value = err.message
  } finally {
    saving.value = false
    busyText.value = ''
  }
}

async function toggle(rule) {
  busyId.value = rule.id
  busyText.value = rule.enabled ? '正在收尾当前触发状态…' : '正在回放历史状态，请稍候…'
  error.value = ''
  try {
    await setRuleEnabled(rule.id, !rule.enabled)
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busyId.value = null
    busyText.value = ''
  }
}

function paramText(rule) {
  if (rule.type === 'oversold') return `${rule.window} 日 · 阈值 ${rule.threshold}%`
  if (rule.type === 'volume_surge') return `${rule.window} 日均量 · 量比 ≥ ${rule.threshold}`
  if (rule.type === 'volume_shrink') return `${rule.window} 日均量 · 量比 ≤ ${rule.threshold}`
  if (rule.type === 'breakout') return `${rule.window} 日最高`
  return `${rule.window} 日均线`
}

function scopeText(rule) {
  return rule.scope === 'single' ? `${rule.scopeLabel} · ${rule.scopeCode}` : `${rule.scopeLabel}（${rule.scopeCount} 只）`
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">规则</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          共 {{ items.length }} 条，{{ items.filter((r) => r.enabled).length }} 条启用中
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" /> 刷新
        </Button>
        <Button size="sm" :disabled="saving" @click="openCreate">
          <Plus class="h-3.5 w-3.5" /> 新建规则
        </Button>
      </div>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <Card v-if="showForm" class="mb-4">
      <CardHeader class="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>{{ isEditing ? '修改规则' : '新建规则' }}</CardTitle>
          <CardDescription class="mt-1">
            {{ isEditing
              ? '改时间窗或阈值会先收尾当前触发状态，新参数从下一个求值日起算'
              : '创建后会先按历史行情回放一遍，把触发状态算到昨天' }}
          </CardDescription>
        </div>
        <Button variant="ghost" size="icon" :disabled="saving" @click="closeForm">
          <X class="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-type">规则类型</label>
            <select
              id="rule-type"
              v-model="form.type"
              :disabled="isEditing"
              class="h-10 w-full rounded-lg border border-input bg-background px-2 text-sm disabled:opacity-60"
              @change="onTypeChange"
            >
              <option v-for="(label, type) in RULE_TYPE_LABELS" :key="type" :value="type">{{ label }}</option>
            </select>
            <p v-if="isEditing" class="mt-1 text-xs text-muted-foreground">类型不可修改，需要换类型请新建</p>
          </div>

          <div>
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-name">名称</label>
            <Input id="rule-name" v-model="form.name" placeholder="例如：均线 20 日上穿" />
          </div>

          <div v-if="!isEditing">
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-scope">标的范围</label>
            <select
              id="rule-scope"
              v-model="form.scope"
              class="h-10 w-full rounded-lg border border-input bg-background px-2 text-sm"
            >
              <option value="watchlist">全部自选</option>
              <option value="single">指定单只</option>
            </select>
          </div>

          <div v-if="!isEditing && form.scope === 'single'">
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-code">标的代码</label>
            <Input id="rule-code" v-model="form.scopeCode" placeholder="sh.600000" />
          </div>

          <div>
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-window">时间窗（交易日）</label>
            <Input id="rule-window" v-model="form.window" type="number" min="2" />
          </div>

          <div v-if="needsThreshold">
            <label class="mb-1 block text-xs text-muted-foreground" for="rule-threshold">阈值</label>
            <Input id="rule-threshold" v-model="form.threshold" type="number" step="0.1" />
            <p class="mt-1 text-xs text-muted-foreground">{{ thresholdHint(form.type) }}</p>
          </div>
        </div>

        <p v-if="formError" class="mt-4 text-sm text-destructive">{{ formError }}</p>

        <div class="mt-5 flex items-center gap-2">
          <Button :disabled="saving" @click="submit">
            <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
            {{ saving ? '处理中…' : isEditing ? '保存修改' : '创建并启用' }}
          </Button>
          <Button variant="ghost" :disabled="saving" @click="closeForm">取消</Button>
          <span v-if="busyText" class="text-xs text-muted-foreground">{{ busyText }}</span>
        </div>
      </CardContent>
    </Card>

    <p v-if="!loading && items.length === 0" class="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
      还没有规则。点「新建规则」开始，创建后会自动回放历史状态。
    </p>

    <div v-else class="space-y-3">
      <Card v-for="rule in items" :key="rule.id">
        <CardContent class="flex flex-wrap items-center gap-4 pt-6">
          <div class="min-w-[200px] flex-1">
            <div class="flex items-center gap-2">
              <span class="font-medium">{{ rule.name }}</span>
              <Badge :variant="rule.enabled ? 'success' : 'secondary'">
                {{ rule.enabled ? '启用中' : '已停用' }}
              </Badge>
            </div>
            <p class="mt-1 text-sm text-muted-foreground">
              {{ rule.typeLabel }} · {{ paramText(rule) }}
            </p>
            <p class="mt-0.5 text-xs text-muted-foreground">
              {{ scopeText(rule) }}
            </p>
          </div>

          <div class="text-right text-xs text-muted-foreground">
            <p>最近触发</p>
            <p class="mt-0.5 font-mono text-sm text-foreground">{{ rule.lastTriggeredAt || '—' }}</p>
          </div>

          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" :disabled="busyId !== null" @click="openEdit(rule)">
              <Pencil class="h-3.5 w-3.5" /> 编辑
            </Button>
            <Button
              :variant="rule.enabled ? 'outline' : 'default'"
              size="sm"
              :disabled="busyId !== null"
              @click="toggle(rule)"
            >
              <Loader2 v-if="busyId === rule.id" class="h-3.5 w-3.5 animate-spin" />
              <Power v-else class="h-3.5 w-3.5" />
              {{ rule.enabled ? '停用' : '启用' }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>

    <p v-if="busyText" class="mt-4 text-xs text-muted-foreground">{{ busyText }}</p>
  </AppShell>
</template>
