<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronRight, PanelLeftClose } from 'lucide-vue-next'
import { NAV_GROUPS, isNavActive } from '../lib/nav'
import { cn } from '../lib/utils'

/**
 * 共用侧栏：控制台与所有子页都用这一份，导航条目见 `lib/nav.js`。
 *
 * 折叠状态由使用方持有（`v-model:collapsed`），因为它同时决定正文的左边距。
 */
defineProps({
  unread: { type: Number, default: null },
})

const collapsed = defineModel('collapsed', { type: Boolean, default: false })

const route = useRoute()
const router = useRouter()

// 只有停在控制台时才谈「当前分区」，其他页面一律没有分区高亮
const activeSection = ref('')

watch(
  () => route.fullPath,
  () => {
    activeSection.value = route.path === '/dashboard' ? route.hash.replace('#', '') : ''
  },
  { immediate: true }
)

/** 控制台内的分区：同页就平滑滚过去，跨页则带着 hash 跳回来由路由滚动。 */
async function goSection(section) {
  if (route.path !== '/dashboard') {
    await router.push({ path: '/dashboard', hash: `#${section}` })
    return
  }
  activeSection.value = section
  document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  // 同步地址栏，刷新或分享后还能落回同一个分区
  router.replace({ path: '/dashboard', hash: `#${section}` })
}

function goTop() {
  activeSection.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
  router.replace({ path: '/dashboard' })
}

function navigate(item) {
  if (item.section) {
    goSection(item.section)
    return
  }
  // 已在控制台还点控制台：回到顶部，不要走一次被路由忽略的重复跳转
  if (item.to === '/dashboard' && route.path === '/dashboard') {
    goTop()
    return
  }
  router.push(item.to)
}
</script>

<template>
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
      <div v-for="group in NAV_GROUPS" :key="group.label">
        <p v-if="!collapsed" class="mb-1.5 px-2 text-[11px] font-medium text-muted-foreground">{{ group.label }}</p>
        <button
          v-for="item in group.items"
          :key="item.label"
          :title="item.label"
          class="mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
          :class="[
            isNavActive(item, route.path, activeSection) ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground/80',
            collapsed ? 'justify-center' : '',
          ]"
          @click="navigate(item)"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" />
          <span v-if="!collapsed" class="flex-1 truncate">{{ item.label }}</span>
          <span
            v-if="item.badge && unread && !collapsed"
            class="rounded-full bg-warning-soft px-1.5 text-[11px] font-medium text-warning"
          >{{ unread }}</span>
          <ChevronRight v-if="!collapsed && item.leave" class="h-3.5 w-3.5 text-muted-foreground" />
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
</template>
