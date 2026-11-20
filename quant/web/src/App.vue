<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchHealth } from './api/client'

const health = ref(null)
const error = ref('')
const loading = ref(false)

const rows = computed(() => [
  { label: '后端版本', value: health.value?.version },
  { label: '数据目录', value: health.value?.parquetDir, mono: true },
  { label: '原始数据目录', value: health.value?.rawDir, mono: true },
  { label: '时区', value: health.value?.timezone },
  { label: '服务器时间', value: health.value?.serverTime, mono: true },
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    health.value = await fetchHealth()
  } catch (e) {
    health.value = null
    error.value = e.message
  } finally {
    loading.value = false
  }
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
      <div class="row">
        <span class="label">服务状态</span>
        <span v-if="loading" class="value muted">检测中…</span>
        <span v-else-if="health" class="value status ok"><i class="dot" />在线</span>
        <span v-else class="value status bad"><i class="dot" />离线</span>
      </div>

      <div v-for="row in rows" :key="row.label" class="row">
        <span class="label">{{ row.label }}</span>
        <span class="value" :class="{ mono: row.mono }">{{ row.value ?? '—' }}</span>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="retry" :disabled="loading" @click="load">重新检测</button>
    </section>

    <footer class="foot">本平台仅提供数据分析，不构成投资建议</footer>
  </main>
</template>

<style scoped>
.page {
  max-width: 720px;
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

.error {
  margin: 16px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(224, 92, 92, 0.1);
  color: var(--bad);
}

.retry {
  margin-top: 16px;
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
