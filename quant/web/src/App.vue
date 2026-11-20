<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchDataStatus, fetchHealth } from './api/client'

const health = ref(null)
const status = ref(null)
const error = ref('')
const loading = ref(false)

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

onMounted(load)
</script>

<template>
  <main class="page">
    <header class="head">
      <h1>Quant Platform</h1>
      <p class="sub">A 股数据分析与预警 · 只读行情，不接交易</p>
    </header>

    <section class="card">
      <h2 class="title">服务状态</h2>
      <div class="row">
        <span class="label">状态</span>
        <span v-if="loading" class="value muted">检测中…</span>
        <span v-else-if="health" class="value status ok"><i class="dot" />在线</span>
        <span v-else class="value status bad"><i class="dot" />离线</span>
      </div>

      <div v-for="row in healthRows" :key="row.label" class="row">
        <span class="label">{{ row.label }}</span>
        <span class="value" :class="{ mono: row.mono }">{{ row.value ?? '—' }}</span>
      </div>
    </section>

    <section class="card">
      <h2 class="title">数据状态</h2>

      <div class="row">
        <span class="label">总行数</span>
        <span class="value mono">{{ status ? status.totalRows.toLocaleString() : '—' }}</span>
      </div>
      <div class="row">
        <span class="label">日期范围</span>
        <span class="value mono">{{ dateRange }}</span>
      </div>
      <div class="row">
        <span class="label">最近导入</span>
        <span class="value">
          <template v-if="lastImport">
            <span :class="lastImport.ok ? 'ok-text' : 'bad-text'">{{ lastImport.status }}</span>
            · {{ lastImport.rows }} 行 · {{ lastImport.days }} 个交易日
            <span class="muted mono"> {{ lastImport.time }}</span>
          </template>
          <span v-else class="muted">尚无导入记录</span>
        </span>
      </div>
      <p v-if="lastImport?.message" class="notice">{{ lastImport.message }}</p>

      <div class="row">
        <span class="label">缺失交易日</span>
        <span class="value">
          <span v-if="missingDates.length === 0" class="muted">无</span>
          <span v-else class="chips">
            <span v-for="day in missingDates.slice(0, 12)" :key="day" class="chip mono">{{ day }}</span>
            <span v-if="missingDates.length > 12" class="muted">还有 {{ missingDates.length - 12 }} 个</span>
          </span>
        </span>
      </div>

      <p v-if="status && status.totalRows === 0" class="hint">
        尚无行情数据。把历史 CSV 按 <code>daily/YYYY-MM-DD.csv</code>、<code>factors/YYYY-MM-DD.csv</code>
        放进原始数据目录后，运行 <code>python -m app.import_history</code>。
      </p>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <button class="retry" :disabled="loading" @click="load">刷新</button>

    <footer class="foot">本平台仅提供数据分析，不构成投资建议</footer>
  </main>
</template>

<style scoped>
.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 24px;
}

.head h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.5px;
}

.sub {
  margin: 6px 0 28px;
  color: var(--muted);
}

.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 20px 20px;
  margin-bottom: 16px;
}

.title {
  margin: 16px 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 1px;
}

.row {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-of-type {
  border-bottom: none;
}

.label {
  width: 96px;
  flex: none;
  color: var(--muted);
}

.value {
  flex: 1;
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
}

.muted {
  color: var(--muted);
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.ok {
  color: var(--ok);
}

.bad {
  color: var(--bad);
}

.ok-text {
  color: var(--ok);
}

.bad-text {
  color: var(--bad);
}

.chips {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.chip {
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(127, 127, 127, 0.12);
}

.notice,
.hint {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.1);
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.hint code {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
}

.error {
  margin: 0 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(224, 92, 92, 0.1);
  color: var(--bad);
}

.retry {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--accent);
  font-size: 14px;
  cursor: pointer;
}

.retry:disabled {
  opacity: 0.5;
  cursor: default;
}

.foot {
  margin-top: 24px;
  text-align: center;
  color: var(--muted);
  font-size: 12px;
}
</style>
