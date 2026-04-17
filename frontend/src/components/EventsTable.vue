<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'

const props = defineProps({ events: { type: Array, required: true } })
const store = useAppStore()
const { t } = useTranslation()

const animClass = computed(() => {
  if (store.animation === 'push-down') return 'anim-push-down'
  if (store.animation === 'slide-in') return 'anim-slide-in'
  return 'anim-beam-drop'
})

function fmtDate(iso) {
  try { return new Date(iso).toLocaleString('de-DE') } catch { return iso }
}

function direction(ev) {
  const owned = new Set(store.wallets.map(w => w.id))
  if (ev.is_internal) return 'INTERNAL'
  if (owned.has(ev.destination_addr)) return 'IN'
  if (owned.has(ev.source_address)) return 'OUT'
  return '—'
}

function flashClass(ev) {
  const d = direction(ev)
  if (d === 'IN') return 'flash-in'
  if (d === 'OUT') return 'flash-out'
  return ''
}

function shortAddr(a) {
  if (!a) return '—'
  return a.length > 16 ? `${a.slice(0, 8)}…${a.slice(-6)}` : a
}

function valueEur(ev) {
  if (!ev.amount_qubic || !ev.qubic_eur_rate) return '—'
  return (ev.amount_qubic * ev.qubic_eur_rate).toFixed(4) + ' €'
}
</script>

<template>
  <div class="card overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-qubic-border text-gray-400 text-xs uppercase">
          <tr>
            <th class="text-left p-3">{{ t('event.date') }}</th>
            <th class="text-left p-3">{{ t('event.direction') }}</th>
            <th class="text-left p-3">{{ t('event.amount') }}</th>
            <th class="text-left p-3">{{ t('event.rate_eur') }}</th>
            <th class="text-left p-3">{{ t('event.value_eur') }}</th>
            <th class="text-left p-3">Source</th>
            <th class="text-left p-3">Destination</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!events.length">
            <td colspan="7" class="text-center p-8 text-gray-500">{{ t('event.none') }}</td>
          </tr>
          <tr v-for="ev in events" :key="ev.id"
              :class="[animClass, flashClass(ev), 'border-b border-qubic-border/50 hover:bg-qubic-bg/50']">
            <td class="p-3 text-xs">{{ fmtDate(ev.timestamp) }}</td>
            <td class="p-3">
              <span v-if="direction(ev) === 'IN'" class="text-green-400">▲ IN</span>
              <span v-else-if="direction(ev) === 'OUT'" class="text-red-400">▼ OUT</span>
              <span v-else-if="direction(ev) === 'INTERNAL'" class="text-gray-400">⇄ INT</span>
              <span v-else class="text-gray-500">—</span>
            </td>
            <td class="p-3 font-mono">{{ Number(ev.amount_qubic || 0).toLocaleString('de-DE') }} QU</td>
            <td class="p-3 font-mono text-xs">{{ ev.qubic_eur_rate ? ev.qubic_eur_rate.toFixed(10).replace(/\.?0+$/, '') : '—' }}</td>
            <td class="p-3 font-mono">{{ valueEur(ev) }}</td>
            <td class="p-3 font-mono text-xs text-gray-400">{{ shortAddr(ev.source_address) }}</td>
            <td class="p-3 font-mono text-xs text-gray-400">{{ shortAddr(ev.destination_addr) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
