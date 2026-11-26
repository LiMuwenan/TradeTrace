<script setup>
import { useRouter } from 'vue-router'

// 页面仍然只管 emit：具体跳到哪条路由由入口统一决定
const router = useRouter()
</script>

<template>
  <router-view v-slot="{ Component }">
    <component
      :is="Component"
      @enter="router.push('/dashboard')"
      @leave="router.push('/')"
    />
  </router-view>
</template>
