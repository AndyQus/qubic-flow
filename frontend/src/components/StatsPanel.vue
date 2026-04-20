<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'

const { t } = useTranslation()
const stats = ref(null)

async function load() {
  try { stats.value = await api.stats.current() } catch (e) { console.error(e) }
}

onMounted(load)
setInterval(load, 60_000)

const keys = ['hour', 'day', 'epoch', 'month', 'year']

const icons = {
  hour:  'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  day:   'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
  epoch: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  month: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  year:  'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('de-DE')
}
</script>

<template>
  <div v-if="stats" class="grid grid-cols-2 md:grid-cols-5 gap-3">
    <div v-for="k in keys" :key="k" class="card !p-3">
      <div class="flex items-center gap-1 mb-1">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" :d="icons[k]"/>
        </svg>
        <span class="text-[10px] uppercase tracking-wide text-gray-500">{{ t(`stats.${k}`) }}</span>
      </div>
      <div class="text-lg font-bold text-qubic-teal leading-tight">{{ fmt(stats[k].current.volume_qubic) }} QU</div>
      <div class="text-xs text-gray-400">{{ fmt(stats[k].current.count) }} {{ t('stats.count') }}</div>
    </div>
  </div>
</template>
