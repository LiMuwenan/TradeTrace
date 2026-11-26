<script setup>
import { cn } from '../../lib/utils'

// 必须显式声明 modelValue 并回传 update:modelValue：组件上的 v-model 不会自动落到内部 input 上。
// 漏了这两件事，输入框看着能打字，但父组件的绑定值一直是空，搜索按钮的 disabled 也就永远不解除。
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  class: { type: [String, Array, Object], default: '' },
})

const emit = defineEmits(['update:modelValue'])

function onInput(event) {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <input
    :value="modelValue ?? ''"
    :class="cn(
      'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50',
      props.class
    )"
    @input="onInput"
  />
</template>
