<script setup>
import { ArrowRight, BarChart3, BellRing, Radar } from 'lucide-vue-next'
import Button from './ui/Button.vue'

defineEmits(['enter'])

const features = [
  {
    icon: Radar,
    title: '只读行情',
    description: '全市场日 K 与因子数据，按交易日归档，不做任何写操作。',
  },
  {
    icon: BarChart3,
    title: '可判定规则',
    description: '标的范围 + 指标 + 阈值 + 时间窗，收盘后按后复权价求值。',
  },
  {
    icon: BellRing,
    title: '收盘预警',
    description: '触发即成记录，附当时价格与指标值；另有日报汇总。',
  },
]

const rows = [
  { label: 'SH.600519', status: '已归档' },
  { label: 'SZ.000858', status: '已归档' },
  { label: 'SH.601318', status: '已归档' },
  { label: 'SZ.300750', status: '已归档' },
]
</script>

<template>
  <div class="min-h-screen bg-background">
    <header class="sticky top-0 z-20 border-b bg-background/85 backdrop-blur">
      <div class="container flex h-14 items-center justify-between">
        <div class="flex items-center gap-2 font-semibold tracking-tight">
          <span class="grid h-6 w-6 place-items-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">Q</span>
          Quant Platform
        </div>
        <nav class="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
          <a href="#platform" class="transition-colors hover:text-foreground">平台</a>
          <a href="#capabilities" class="transition-colors hover:text-foreground">能力</a>
          <a href="#about" class="transition-colors hover:text-foreground">关于</a>
        </nav>
        <Button size="sm" @click="$emit('enter')">进入控制台</Button>
      </div>
    </header>

    <section class="hero-glow relative isolate overflow-hidden border-b">
      <div class="container relative z-10 grid items-center gap-12 py-20 lg:grid-cols-2 lg:py-28">
        <div>
          <p class="mb-5 text-xs font-semibold uppercase tracking-[0.22em] text-brand">
            A 股量化数据基础设施
          </p>
          <h1 class="text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-[3.4rem]">
            看清数据，<br />再决定下一步。
          </h1>
          <p class="mt-6 max-w-lg text-[15px] leading-7 text-muted-foreground">
            把全市场日 K、因子与自选管理放在一处。用可判定的规则盯盘，收盘后生成预警与日报——
            只读行情，不接交易，不输出投资建议。
          </p>
          <div class="mt-8 flex flex-wrap items-center gap-3">
            <Button size="lg" @click="$emit('enter')">
              进入控制台 <ArrowRight class="h-4 w-4" />
            </Button>
            <Button variant="outline" size="lg" as="a" href="#platform">了解平台</Button>
          </div>
          <p class="mt-5 flex items-center gap-2 text-xs text-muted-foreground">
            <span class="h-1.5 w-1.5 rounded-full bg-down" />
            本地运行 · 数据只在你的机器上
          </p>
        </div>

        <div class="relative z-10 mx-auto w-full max-w-md">
          <div class="overflow-hidden rounded-2xl border bg-card shadow-xl shadow-slate-200/60">
            <div class="flex items-center justify-between border-b px-5 py-4">
              <div>
                <p class="text-sm font-semibold">已归档标的</p>
                <p class="mt-0.5 text-xs text-muted-foreground">样例展示 · 与实际数据无关</p>
              </div>
              <span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                <span class="h-1.5 w-1.5 rounded-full bg-emerald-500" /> 就绪
              </span>
            </div>
            <div class="divide-y">
              <div v-for="row in rows" :key="row.label" class="flex items-center justify-between px-5 py-3.5">
                <div class="flex items-center gap-3">
                  <span class="grid h-7 w-7 place-items-center rounded-md bg-secondary text-[10px] font-medium text-muted-foreground">日K</span>
                  <span class="font-mono text-xs">{{ row.label }}</span>
                </div>
                <span class="text-xs text-muted-foreground">{{ row.status }}</span>
              </div>
            </div>
            <div class="flex items-center justify-between border-t bg-secondary/40 px-5 py-4">
              <div>
                <p class="text-sm font-medium">后复权口径</p>
                <p class="text-xs text-muted-foreground">跨日比较一律使用</p>
              </div>
              <BarChart3 class="h-4 w-4 text-muted-foreground" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="platform" class="container grid gap-10 py-16 lg:grid-cols-[0.85fr_1.15fr]">
      <div>
        <p class="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-brand">平台</p>
        <h2 class="text-balance text-3xl font-semibold leading-tight tracking-tight">
          基础设施，<br />不挡你的路。
        </h2>
        <p class="mt-4 max-w-sm leading-6 text-muted-foreground">
          数据、规则与预警各司其职。你只需要关心想盯什么，而不是数据怎么落盘。
        </p>
      </div>
      <div class="space-y-3">
        <div v-for="(feature, index) in features" :key="feature.title" class="flex gap-4 rounded-xl border bg-card p-5">
          <div class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent text-accent-foreground">
            <component :is="feature.icon" class="h-4 w-4" />
          </div>
          <div class="flex-1">
            <p class="font-medium">{{ feature.title }}</p>
            <p class="mt-1 text-sm leading-6 text-muted-foreground">{{ feature.description }}</p>
          </div>
          <span class="font-mono text-xs text-muted-foreground/70">0{{ index + 1 }}</span>
        </div>
      </div>
    </section>

    <section id="capabilities" class="border-t">
      <div class="container grid gap-4 py-16 sm:grid-cols-3">
        <div v-for="item in features" :key="item.title" class="border-l pl-5">
          <p class="font-medium">{{ item.title }}</p>
          <p class="mt-1 text-sm text-muted-foreground">{{ item.description }}</p>
        </div>
      </div>
    </section>

    <footer id="about" class="border-t">
      <div class="container flex flex-wrap items-center justify-between gap-3 py-8 text-xs text-muted-foreground">
        <span>Quant Platform · 本平台仅提供数据分析，不构成投资建议</span>
        <Button variant="link" size="sm" class="h-auto p-0" @click="$emit('enter')">打开控制台 →</Button>
      </div>
    </footer>
  </div>
</template>
