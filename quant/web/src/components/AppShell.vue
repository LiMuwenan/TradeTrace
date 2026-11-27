<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import SideNav from './SideNav.vue'
import { cn } from '../lib/utils'

defineProps({
  unread: { type: Number, default: null },
})

const route = useRoute()
const collapsed = ref(false)

const PAGE_TITLES = {
  '/dashboard': '控制台',
  '/alerts': '预警',
  '/rules': '规则',
  '/reports': '日报',
  '/pipeline': '运行记录',
  '/settings/notification': '通知设置',
}

const pageTitle = computed(() => {
  if (route.path.startsWith('/stocks')) return '个股详情'
  const matched = Object.keys(PAGE_TITLES).find(
    (path) => route.path === path || route.path.startsWith(`${path}/`)
  )
  return matched ? PAGE_TITLES[matched] : '控制台'
})
</script>

<template>
  <div class="min-h-screen bg-secondary/40">
    <SideNav v-model:collapsed="collapsed" :unread="unread" />

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
