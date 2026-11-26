<script setup>
import { ref } from 'vue'
import Dashboard from './components/Dashboard.vue'
import LandingPage from './components/LandingPage.vue'

const view = ref('landing')
</script>

<template>
  <LandingPage v-if="view === 'landing'" @enter="view = 'dashboard'" />
  <Dashboard v-else @leave="view = 'landing'" />
</template>
