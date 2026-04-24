<script setup>
import { useTranslation } from 'i18next-vue'
import { useAppStore } from '../stores/app'

defineProps({
  stats:   { type: Object,  default: null },
  loading: { type: Boolean, default: true },
})

const { t } = useTranslation()
const store = useAppStore()

const keys = ['hour', 'day', 'epoch', 'month', 'year']

const icons = {
  hour:  'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  day:   'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
  epoch: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  month: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  year:  'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

const colors = {
  hour:  'text-sky-400',
  day:   'text-amber-400',
  epoch: 'text-violet-400',
  month: 'text-emerald-400',
  year:  'text-rose-400',
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString(store.locale)
}
</script>

<template>
  <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
    <div v-for="k in keys" :key="k" class="card !p-3 cq-panel">
      <div class="flex items-center gap-1 mb-1">
        <svg xmlns="http://www.w3.org/2000/svg" :class="['w-3 h-3 flex-shrink-0', colors[k]]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" :d="icons[k]"/>
        </svg>
        <span :class="['text-sm uppercase tracking-wide', colors[k]]">{{ t(`stats.${k}`) }} QUBIC</span>
      </div>
      <div class="min-h-[3.5rem] flex flex-col justify-center">
        <template v-if="loading">
          <div class="flex justify-center">
            <svg class="w-5 h-5 text-gray-500 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
            </svg>
          </div>
        </template>
        <template v-else>
          <div class="text-base sm:text-xl font-bold text-qubic-teal whitespace-nowrap">{{ stats ? fmt(stats[k].current.volume_qubic) : '—' }}</div>
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-xs font-semibold text-violet-400">{{ stats ? fmt(stats[k].current.event_count) : '—' }} Events</span>
            <span class="text-xs font-semibold text-amber-400">{{ stats ? fmt(stats[k].current.tx_count) : '—' }} TX</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
