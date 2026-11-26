<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, LayoutDashboard, Settings2 } from 'lucide-vue-next'
import Badge from './ui/Badge.vue'
import { cn } from '../lib/utils'

const props = defineProps({
  unread: { type: Number, default: null },
})

const route = useRoute()
const router = useRouter()

const links = [
  { label: '控制台', to: '/dashboard', icon: LayoutDashboard, match: '/dashboard' },
  { label: '预警', to: '/alerts', icon: Bell, match: '/alerts' },
  { label: '通知设置', to: '/settings/notification', icon: Settings2, match: '/settings/notification' },
]

const current = computed(() => links.find((link) => route.path.startsWith(link.match))?.to)
</script>

<template>
  <div class="min-h-screen bg-secondary/40">
    <header class="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
      <div class="container flex h-14 items-center gap-6">
        <button class="flex items-center gap-2" @click="router.push('/')">
          <span class="grid h-6 w-6 place-items-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">Q</span>
          <span class="text-sm font-semibold">Quant Platform</span>
        </button>

        <nav class="flex items-center gap-1">
          <button
            v-for="link in links"
            :key="link.to"
            :class="cn(
              'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors',
              current === link.to
                ? 'bg-accent font-medium text-accent-foreground'
                : 'text-foreground/70 hover:bg-accent/60 hover:text-accent-foreground'
            )"
            @click="router.push(link.to)"
          >
            <component :is="link.icon" class="h-4 w-4" />
            {{ link.label }}
            <Badge v-if="link.to === '/alerts' && unread" variant="warning" class="ml-1">{{ unread }}</Badge>
          </button>
        </nav>

        <div class="ml-auto text-xs text-muted-foreground">只读行情 · 不构成投资建议</div>
      </div>
    </header>

    <main class="container py-8">
      <slot />
    </main>
  </div>
</template>
