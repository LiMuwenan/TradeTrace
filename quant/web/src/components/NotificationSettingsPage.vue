<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { CheckCircle2, Send, XCircle } from 'lucide-vue-next'
import {
  fetchNotificationLog,
  fetchNotificationSettings,
  saveNotificationSettings,
  sendTestNotification,
} from '../api/client'
import { PUSH_RESULT_LABELS } from '../lib/alertFormat'
import AppShell from './AppShell.vue'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import CardContent from './ui/CardContent.vue'
import CardDescription from './ui/CardDescription.vue'
import CardHeader from './ui/CardHeader.vue'
import CardTitle from './ui/CardTitle.vue'
import Input from './ui/Input.vue'

const config = ref(null)
const form = reactive({
  ntfyServer: '',
  ntfyTopic: '',
  ntfyToken: '',
  emailTo: '',
  smtpHost: '',
  smtpPort: '',
  smtpUser: '',
  smtpPassword: '',
  smtpStarttls: true,
  dailyLimit: 50,
  limitEnabled: true,
})

const logs = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const LOG_PAGE_SIZE = 10
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saved = ref('')
const testing = ref(false)
const testResult = ref(null)

const usage = computed(() => config.value?.usage || null)
const usageText = computed(() => {
  if (!usage.value) return '—'
  const limit = usage.value.limit
  return limit === null ? `${usage.value.attempted} 条（未启用上限）` : `${usage.value.attempted} / ${limit} 条`
})

function fill(data) {
  form.ntfyServer = data.ntfyServer || ''
  form.ntfyTopic = data.ntfyTopic || ''
  form.emailTo = data.emailTo || ''
  form.smtpHost = data.smtpHost || ''
  form.smtpPort = data.smtpPort ?? ''
  form.smtpUser = data.smtpUser || ''
  form.smtpStarttls = Boolean(data.smtpStarttls)
  form.dailyLimit = data.dailyLimit ?? 50
  form.limitEnabled = Boolean(data.limitEnabled)
  // 凭据不回显：输入框留空表示保留原值
  form.ntfyToken = ''
  form.smtpPassword = ''
}

async function loadLogs(reset = false) {
  if (reset) logPage.value = 1
  const log = await fetchNotificationLog({ page: logPage.value, pageSize: LOG_PAGE_SIZE })
  logs.value = reset ? log.items : [...logs.value, ...log.items]
  logTotal.value = log.total
}

function moreLogs() {
  logPage.value += 1
  loadLogs().catch((err) => {
    error.value = err.message
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [settings] = await Promise.all([fetchNotificationSettings(), loadLogs(true)])
    config.value = settings
    fill(settings)
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function payload() {
  const body = {
    ntfyServer: form.ntfyServer,
    ntfyTopic: form.ntfyTopic,
    emailTo: form.emailTo,
    smtpHost: form.smtpHost,
    smtpUser: form.smtpUser,
    smtpPort: form.smtpPort === '' ? null : Number(form.smtpPort),
    smtpStarttls: form.smtpStarttls,
    dailyLimit: Number(form.dailyLimit),
    limitEnabled: form.limitEnabled,
  }
  if (form.ntfyToken) body.ntfyToken = form.ntfyToken
  if (form.smtpPassword) body.smtpPassword = form.smtpPassword
  return body
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = ''
  try {
    const data = await saveNotificationSettings(payload())
    config.value = data
    fill(data)
    saved.value = '已保存'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

async function clearCredential(field) {
  saving.value = true
  error.value = ''
  try {
    const data = await saveNotificationSettings({ [field]: '' })
    config.value = data
    fill(data)
    saved.value = field === 'ntfyToken' ? '已清除 ntfy 访问令牌' : '已清除 SMTP 密码'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await sendTestNotification()
    await loadLogs(true)
  } catch (err) {
    testResult.value = { ok: false, channel: null, error: err.message }
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="mb-6">
      <h1 class="text-xl font-semibold tracking-tight">通知设置</h1>
      <p class="mt-1 text-sm text-muted-foreground">
        预警产生后推送到手机。ntfy 走不通时自动改发邮件，两边都失败只记录，不影响预警入库。
      </p>
    </div>

    <p v-if="error" class="mb-4 rounded-lg border border-destructive bg-background px-3 py-2 text-sm text-destructive">
      {{ error }}
    </p>

    <div v-if="loading" class="p-10 text-center text-sm text-muted-foreground">加载中…</div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <div class="space-y-4 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>ntfy 推送</CardTitle>
            <CardDescription>服务在局域网内，只能主动向外发请求，因此用 ntfy 的 HTTP 推送。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="ntfy-server">服务地址</label>
                <Input
                  id="ntfy-server"
                  :value="form.ntfyServer"
                  placeholder="https://ntfy.sh"
                  @input="form.ntfyServer = $event.target.value"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="ntfy-topic">主题名</label>
                <Input
                  id="ntfy-topic"
                  :value="form.ntfyTopic"
                  placeholder="一段足够长的随机串"
                  class="font-mono"
                  @input="form.ntfyTopic = $event.target.value"
                />
              </div>
            </div>

            <p class="rounded-lg border border-warning bg-warning-soft px-3 py-2 text-xs text-warning">
              主题名等同于密码：任何知道它的人都能订阅你的预警。请用足够长的随机串，不要用 <code class="font-mono">stock</code> 这类可猜的词；怀疑泄露就换一个。
            </p>

            <div>
              <label class="mb-1 block text-xs text-muted-foreground" for="ntfy-token">
                访问令牌（可选，自建服务限流时才需要）
              </label>
              <div class="flex gap-2">
                <Input
                  id="ntfy-token"
                  type="password"
                  :value="form.ntfyToken"
                  :placeholder="config?.ntfyTokenConfigured ? '已配置，留空表示不修改' : '未配置'"
                  @input="form.ntfyToken = $event.target.value"
                />
                <Button
                  v-if="config?.ntfyTokenConfigured"
                  variant="ghost"
                  size="sm"
                  :disabled="saving"
                  @click="clearCredential('ntfyToken')"
                >清除</Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>邮件兜底</CardTitle>
            <CardDescription>ntfy 超时或报错时改发邮件；两者都失败时预警仍留在列表里，重跑可补推。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="email-to">收件邮箱</label>
                <Input
                  id="email-to"
                  :value="form.emailTo"
                  placeholder="me@example.com"
                  @input="form.emailTo = $event.target.value"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="smtp-host">SMTP 主机</label>
                <Input
                  id="smtp-host"
                  :value="form.smtpHost"
                  placeholder="smtp.example.com"
                  @input="form.smtpHost = $event.target.value"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="smtp-port">端口</label>
                <Input
                  id="smtp-port"
                  type="number"
                  :value="form.smtpPort"
                  placeholder="465"
                  @input="form.smtpPort = $event.target.value"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs text-muted-foreground" for="smtp-user">账号</label>
                <Input
                  id="smtp-user"
                  :value="form.smtpUser"
                  placeholder="通常与收件邮箱相同"
                  @input="form.smtpUser = $event.target.value"
                />
              </div>
            </div>

            <div>
              <label class="mb-1 block text-xs text-muted-foreground" for="smtp-password">密码 / 授权码</label>
              <div class="flex gap-2">
                <Input
                  id="smtp-password"
                  type="password"
                  :value="form.smtpPassword"
                  :placeholder="config?.smtpPasswordConfigured ? '已配置，留空表示不修改' : '未配置'"
                  @input="form.smtpPassword = $event.target.value"
                />
                <Button
                  v-if="config?.smtpPasswordConfigured"
                  variant="ghost"
                  size="sm"
                  :disabled="saving"
                  @click="clearCredential('smtpPassword')"
                >清除</Button>
              </div>
            </div>

            <label class="flex items-center gap-2 text-sm">
              <input v-model="form.smtpStarttls" type="checkbox" class="h-4 w-4 rounded border-input" />
              使用 STARTTLS（465 端口通常关闭，587 端口通常开启）
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>每日推送上限</CardTitle>
            <CardDescription>按交易日计「尝试投递的条数」：成功、降级、失败都占一次额度。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <label class="flex items-center gap-2 text-sm">
              <input v-model="form.limitEnabled" type="checkbox" class="h-4 w-4 rounded border-input" />
              启用上限
            </label>
            <div class="flex items-end gap-3">
              <div class="w-32">
                <label class="mb-1 block text-xs text-muted-foreground" for="daily-limit">每日最多</label>
                <Input
                  id="daily-limit"
                  type="number"
                  :value="form.dailyLimit"
                  :disabled="!form.limitEnabled"
                  @input="form.dailyLimit = $event.target.value"
                />
              </div>
              <p class="pb-2 text-xs text-muted-foreground">超出的预警只入库，不上手机；在预警列表里照常能翻到。</p>
            </div>
          </CardContent>
        </Card>

        <div class="flex flex-wrap items-center gap-3">
          <Button :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存设置' }}</Button>
          <Button variant="outline" :disabled="testing" @click="sendTest">
            <Send class="h-3.5 w-3.5" /> {{ testing ? '发送中…' : '发送测试通知' }}
          </Button>
          <span v-if="saved" class="flex items-center gap-1 text-xs text-success">
            <CheckCircle2 class="h-3.5 w-3.5" /> {{ saved }}
          </span>
        </div>

        <p
          v-if="testResult"
          class="flex items-start gap-2 rounded-lg border px-3 py-2 text-xs"
          :class="testResult.ok
            ? 'border-success bg-success-soft text-success'
            : 'border-destructive bg-background text-destructive'"
        >
          <CheckCircle2 v-if="testResult.ok" class="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <XCircle v-else class="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span v-if="testResult.ok">已通过 {{ testResult.channel === 'ntfy' ? 'ntfy' : '邮件' }} 送达，请确认手机或邮箱收到。</span>
          <span v-else>{{ testResult.error }}</span>
        </p>
      </div>

      <div class="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>当日用量</CardTitle>
            <CardDescription>按交易日统计，与上限口径一致。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-2 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">交易日</span>
              <span class="font-mono">{{ usage?.date || '—' }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">已尝试投递</span>
              <span class="font-mono">{{ usageText }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-muted-foreground">通道状态</span>
              <span class="flex gap-1">
                <Badge :variant="config?.ntfyReady ? 'success' : 'secondary'">ntfy</Badge>
                <Badge :variant="config?.emailReady ? 'success' : 'secondary'">邮件</Badge>
              </span>
            </div>
            <p v-if="!config?.configured" class="text-xs text-warning">
              至少配置一条通道后，预警才会被投递；未配置时求值只落库。
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>最近投递</CardTitle>
            <CardDescription>设置页的测试通知也会记录在此，但不占每日额度。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-2">
            <p v-if="logs.length === 0" class="text-xs text-muted-foreground">还没有投递记录。</p>
            <ul v-else class="space-y-2 text-xs">
              <li v-for="item in logs" :key="item.id" class="rounded-lg border px-2.5 py-2">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono">{{ item.attemptedAt?.slice(5, 16) }}</span>
                  <Badge :variant="item.result === 'failed' ? 'warning' : 'success'">
                    {{ PUSH_RESULT_LABELS[item.result] || item.result }}
                  </Badge>
                </div>
                <p class="mt-1 text-muted-foreground">
                  {{ item.code || '测试通知' }}
                  <span v-if="item.ruleName"> · {{ item.ruleName }}</span>
                  <span v-if="item.channel"> · {{ item.channel }}</span>
                </p>
                <p v-if="item.detail" class="mt-1 text-[11px] text-muted-foreground">{{ item.detail }}</p>
              </li>
            </ul>
            <Button
              v-if="logs.length < logTotal"
              variant="outline"
              size="sm"
              class="w-full"
              @click="moreLogs"
            >加载更多（{{ logs.length }} / {{ logTotal }}）</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  </AppShell>
</template>
