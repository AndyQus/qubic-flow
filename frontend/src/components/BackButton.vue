<script setup>
defineProps({
  label: { type: String, required: true },
})
defineEmits(['click'])
</script>

<template>
  <button
    class="inline-flex items-center gap-1 rounded-md bg-qubic-teal text-gray-900
           text-xs font-medium px-2 py-0.5 transition-colors
           hover:bg-qubic-cyan disabled:opacity-50"
    @click="$emit('click')"
  >
    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <polyline points="15 18 9 12 15 6"/>
    </svg>
    {{ label }}
  </button>
</template>
