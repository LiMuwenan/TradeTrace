<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, ChevronRight, FileText, Home, LayoutDashboard, ListFilter, PanelLeftClose, Settings2 } from 'lucide-vue-next'
import { cn } from '../lib/utils'

defineProps({
  unread: { type: Number, default: null },
})

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

// 与控制台同一套侧栏结构：分组 + 可折叠，条目改为路由跳转
const navGroups = [
  {
    label: '工作区',
    items: [
      { label: '控制台', to: '/dashboard', icon: LayoutDashboard },
      { label: '规则', to: '/rules', icon: ListFilter },
      { label: '预警列表', to: '/alerts', icon: Bell, badge: true },
      { label: '日报', to: '/reports', icon: FileText },
    ],
  },
  {
    label: '设置',
    items: [{ label: '通知设置', to: '/settings/notification', icon: Settings2 }],
  },
  {
    label: '资源',
    items: [{ label: '返回首页', to: '/', icon: Home }],
  },
]

const activePath = computed(() => {
  if (route.path.startsWith('/settings/notification')) return '/settings/notification'
  if (route.path.startsWith('/alerts')) return '/alerts'
  if (route.path.startsWith('/reports')) return '/reports'
  return route.path
})

const PAGE_TITLES = {
  '/alerts': '预警',
  '/rules': '规则',
  '/reports': '日报',
  '/settings/notification': '通知设置',
}
const pageTitle = computed(() =>
  route.path.startsWith('/stocks') ? '个股详情' : PAGE_TITLES[activePath.value] || '控制台'
)
</script>

<template>
  <div class="min-h-screen bg-secondary/40">
    <aside
      :class="cn(
        'fixed inset-y-0 left-0 z-30 flex flex-col border-r bg-background transition-all duration-200',
        collapsed ? 'w-[68px]' : 'w-[228px]'
      )"
    >
      <button
        class="flex h-14 items-center gap-2 border-b px-4"
        :class="collapsed ? 'justify-center' : ''"
        @click="router.push('/')"
      >
        <span class="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">Q</span>
        <div v-if="!collapsed" class="text-left leading-tight">
          <p class="text-sm font-semibold">Quant Platform</p>
          <p class="text-[11px] text-muted-foreground">A 股数据分析</p>
        </div>
      </button>

      <nav class="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        <div v-for="group in navGroups" :key="group.label">
          <p v-if="!collapsed" class="mb-1.5 px-2 text-[11px] font-medium text-muted-foreground">{{ group.label }}</p>
          <button
            v-for="item in group.items"
            :key="item.label"
            :title="item.label"
            class="mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
            :class="[
              activePath === item.to ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground/80',
              collapsed ? 'justify-center' : '',
            ]"
            @click="router.push(item.to)"
          >
            <component :is="item.icon" class="h-4 w-4 shrink-0" />
            <span v-if="!collapsed" class="flex-1 truncate">{{ item.label }}</span>
            <span
              v-if="item.badge && unread && !collapsed"
              class="rounded-full bg-warning-soft px-1.5 text-[11px] font-medium text-warning"
            >{{ unread }}</span>
            <ChevronRight v-if="!collapsed && item.to === '/'" class="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        </div>
      </nav>

      <div class="border-t p-3">
        <button
          class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          :class="collapsed ? 'justify-center' : ''"
          @click="collapsed = !collapsed"
        >
          <PanelLeftClose class="h-4 w-4" />
          <span v-if="!collapsed">收起侧栏</span>
        </button>
      </div>
    </aside>

    <div :class="cn('transition-all duration-200', collapsed ? 'ml-[68px]' : 'ml-[228px]')">
      <header class="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/95 px-6 backdrop-blur">
        <p class="text-sm font-medium">{{ pageTitle }}</p>
        <p class="text-xs text-muted-foreground">只读行情 · 不构成投资建议</p>
      </header>

      <main class="px-6 py-8">
        <slot />
      </main>
    </div>
  </div>
</template>
