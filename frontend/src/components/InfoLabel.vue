<script setup>
defineProps({
  label:   { type: String, required: true },
  tooltip: { type: String, default: '' },
})
</script>

<template>
  <div class="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-gray-500">
    <span>{{ label }}</span>
    <span v-if="tooltip" :title="tooltip"
          class="cursor-help text-gray-500 hover:text-qubic-teal transition-colors leading-none">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
      </svg>
    </span>
  </div>
</template>
