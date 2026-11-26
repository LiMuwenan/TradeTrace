<script setup>
import { cn } from '../../lib/utils'
defineProps({ class: { type: [String, Array, Object], default: '' } })
</script>

<template>
  <input
    :class="cn(
      'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50',
      $props.class
    )"
  />
</template>
