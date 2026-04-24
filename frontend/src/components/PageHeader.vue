<script setup>
defineProps({
  title: { type: String, required: true },
  hint:  { type: String, default: '' },
})
</script>

<template>
  <div class="flex items-center justify-between gap-3 flex-wrap min-h-10">
    <h1 class="text-xl font-bold">
      {{ title }}
      <span v-if="hint" class="text-sm font-normal text-gray-500 ml-2">· {{ hint }}</span>
    </h1>
    <div v-if="$slots.default" class="flex items-center gap-2 flex-wrap">
      <slot />
    </div>
  </div>
</template>
