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

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('de-DE')
}
</script>

<template>
  <div v-if="stats" class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
    <div v-for="k in keys" :key="k" class="card">
      <div class="text-xs uppercase tracking-wide text-gray-400 mb-2">{{ t(`stats.${k}`) }}</div>
      <div class="text-xl font-bold text-qubic-teal">{{ fmt(stats[k].current.count) }}</div>
      <div class="text-[10px] text-gray-500">{{ t('stats.current') }} · {{ fmt(stats[k].current.volume_qubic) }} QU</div>
      <div class="mt-2 pt-2 border-t border-qubic-border">
        <div class="text-base font-semibold text-gray-300">{{ fmt(stats[k].previous.count) }}</div>
        <div class="text-[10px] text-gray-500">{{ t('stats.previous') }} · {{ fmt(stats[k].previous.volume_qubic) }} QU</div>
      </div>
    </div>
  </div>
</template>
