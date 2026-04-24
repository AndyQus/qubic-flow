<script setup>
defineProps({
  type: { type: String, default: '' },   // 'PRIVATE' | 'BUSINESS' | '' (mixed/unknown)
  size: { type: String, default: 'w-4 h-4' },
})
</script>

<template>
  <!-- BUSINESS: building/company icon in orange -->
  <svg v-if="type === 'BUSINESS'"
       xmlns="http://www.w3.org/2000/svg"
       :class="[size, 'shrink-0 text-orange-400']"
       fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round"
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0H5m14 0h2M5 21H3M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5"/>
  </svg>

  <!-- PRIVATE / default: person icon in teal -->
  <svg v-else
       xmlns="http://www.w3.org/2000/svg"
       :class="[size, 'shrink-0 text-qubic-teal']"
       fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round"
          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
  </svg>
</template>
