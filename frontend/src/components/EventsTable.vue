<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'

const props = defineProps({
  events:  { type: Array, required: true },
  loading: { type: Boolean, default: false },
})
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

function fmtDateShort(iso) {
  try { return new Date(iso).toLocaleDateString('de-DE') } catch { return iso }
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
  if (store.hideAddresses) return '••••••••••••'
  return a.length > 16 ? `${a.slice(0, 6)}…${a.slice(-6)}` : a
}

function maskName(name, addr) {
  if (store.hideAddresses) return '••••••••••••'
  return name || shortAddr(addr)
}

function fmtValue(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_usd_rate : ev.qubic_eur_rate
  if (!ev.amount_qubic || !rate) return '—'
  return (ev.amount_qubic * rate).toFixed(2) + (isUsd ? ' $' : ' €')
}

function fmtRate(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_usd_rate : ev.qubic_eur_rate
  if (!rate) return '—'
  return rate.toFixed(8).replace(/\.?0+$/, '') + (isUsd ? ' $' : ' €')
}

function explorerUrl(addr) {
  return `https://explorer.qubic.org/network/address/${addr}`
}

function counterpart(ev) {
  const owned = new Set(store.wallets.map(w => w.id))
  const dir = direction(ev)
  if (dir === 'IN')  return { addr: ev.source_address,  name: ev.source_name }
  if (dir === 'OUT') return { addr: ev.destination_addr, name: ev.destination_name }
  return { addr: ev.source_address, name: ev.source_name }
}
</script>

<template>
  <div class="card overflow-hidden">
    <div class="px-3 pt-3 pb-1 text-[10px] text-gray-500 uppercase tracking-wide">{{ t('event.last10') }}</div>
    <div v-if="loading" class="p-8 text-center text-gray-500 text-xs">{{ t('common.loading') }}</div>

    <template v-else>
      <!-- Mobile: card list -->
      <div class="sm:hidden divide-y divide-qubic-border/40">
        <div v-if="!events.length" class="p-6 text-center text-gray-500 text-xs">{{ t('event.none') }}</div>
        <div v-for="ev in events" :key="ev.id"
             :class="[
               store.newEventIds.includes(ev.id) ? animClass : '',
               store.newEventIds.includes(ev.id) ? flashClass(ev) : '',
               'p-3 flex items-start gap-3'
             ]">
          <!-- Direction badge -->
          <div class="flex-shrink-0 mt-0.5">
            <span v-if="direction(ev) === 'IN'"       class="text-green-400 text-xs font-bold">▲ IN</span>
            <span v-else-if="direction(ev) === 'OUT'" class="text-red-400 text-xs font-bold">▼ OUT</span>
            <span v-else-if="direction(ev) === 'INTERNAL'" class="text-gray-400 text-xs font-bold">⇄ INT</span>
            <span v-else class="text-gray-500 text-xs">—</span>
          </div>
          <!-- Main info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-xs font-medium">{{ Number(ev.amount_qubic || 0).toLocaleString('de-DE') }} QU</span>
              <span class="text-xs text-gray-400">{{ fmtValue(ev) }}</span>
            </div>
            <div class="text-[10px] text-gray-500 mt-0.5">{{ fmtDate(ev.timestamp) }}</div>
            <!-- Counterpart address -->
            <div v-if="counterpart(ev).addr" class="flex items-center gap-1 mt-1">
              <span class="text-[10px] text-gray-400 font-mono truncate">
                {{ maskName(counterpart(ev).name, counterpart(ev).addr) }}
              </span>
              <a :href="explorerUrl(counterpart(ev).addr)" target="_blank" rel="noopener"
                 class="text-gray-600 hover:text-qubic-teal flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- Desktop: table -->
      <div class="hidden sm:block overflow-x-auto">
        <table class="w-full text-xs">
          <thead class="border-b border-qubic-border text-gray-400 uppercase">
            <tr>
              <th class="text-left px-3 py-1.5">{{ t('event.date') }}</th>
              <th class="text-left px-3 py-1.5">{{ t('event.direction') }}</th>
              <th class="text-left px-3 py-1.5">{{ t('event.amount') }}</th>
              <th class="text-left px-3 py-1.5 hidden lg:table-cell">Kurs {{ store.currency }}</th>
              <th class="text-left px-3 py-1.5">Wert {{ store.currency }}</th>
              <th class="text-left px-3 py-1.5">Source</th>
              <th class="text-left px-3 py-1.5">Destination</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!events.length">
              <td colspan="7" class="text-center p-8 text-gray-500">{{ t('event.none') }}</td>
            </tr>
            <tr v-for="ev in events" :key="ev.id"
                :class="[
                  store.newEventIds.includes(ev.id) ? animClass : '',
                  store.newEventIds.includes(ev.id) ? flashClass(ev) : '',
                  'border-b border-qubic-border/50 hover:bg-qubic-bg/50'
                ]">
              <td class="px-3 py-1.5 text-gray-400 whitespace-nowrap">{{ fmtDate(ev.timestamp) }}</td>
              <td class="px-3 py-1.5">
                <span v-if="direction(ev) === 'IN'"       class="text-green-400 font-medium">▲ IN</span>
                <span v-else-if="direction(ev) === 'OUT'" class="text-red-400 font-medium">▼ OUT</span>
                <span v-else-if="direction(ev) === 'INTERNAL'" class="text-gray-400">⇄ INT</span>
                <span v-else class="text-gray-500">—</span>
              </td>
              <td class="px-3 py-1.5 font-mono">{{ Number(ev.amount_qubic || 0).toLocaleString('de-DE') }} QU</td>
              <td class="px-3 py-1.5 font-mono text-gray-400 hidden lg:table-cell">{{ fmtRate(ev) }}</td>
              <td class="px-3 py-1.5 font-mono">{{ fmtValue(ev) }}</td>
              <!-- Source -->
              <td class="px-3 py-1.5">
                <div v-if="ev.source_address" class="flex items-center gap-1">
                  <span class="font-mono text-gray-300" :title="store.hideAddresses ? '' : ev.source_address">
                    {{ maskName(ev.source_name, ev.source_address) }}
                  </span>
                  <a :href="explorerUrl(ev.source_address)" target="_blank" rel="noopener"
                     class="text-gray-600 hover:text-qubic-teal flex-shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <span v-else class="text-gray-500">—</span>
              </td>
              <!-- Destination -->
              <td class="px-3 py-1.5">
                <div v-if="ev.destination_addr" class="flex items-center gap-1">
                  <span class="font-mono text-gray-300" :title="store.hideAddresses ? '' : ev.destination_addr">
                    {{ maskName(ev.destination_name, ev.destination_addr) }}
                  </span>
                  <a :href="explorerUrl(ev.destination_addr)" target="_blank" rel="noopener"
                     class="text-gray-600 hover:text-qubic-teal flex-shrink-0">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <span v-else class="text-gray-500">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
