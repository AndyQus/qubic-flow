<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import { useQubicUtils } from '../composables/useQubicUtils'

const props = defineProps({
  events:  { type: Array, required: true },
  loading: { type: Boolean, default: false },
  title:   { type: String, default: null },
})
const store = useAppStore()
const { t } = useTranslation()
const { explorerUrl, txUrl, tickUrl, copyAddress, shortAddr } = useQubicUtils()

const ownedIds = computed(() => new Set(store.wallets.map(w => w.id)))

const animClass = computed(() => {
  if (store.animation === 'push-down') return 'anim-push-down'
  if (store.animation === 'slide-in') return 'anim-slide-in'
  return 'anim-beam-drop'
})

function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(store.locale) } catch { return iso }
}

function fmtDateShort(iso) {
  try { return new Date(iso).toLocaleDateString(store.locale) } catch { return iso }
}

function direction(ev) {
  if (ev.is_internal) return 'INTERNAL'
  if (ownedIds.value.has(ev.destination_addr)) return 'IN'
  if (ownedIds.value.has(ev.source_address)) return 'OUT'
  return '—'
}

function flashClass(ev) {
  const d = direction(ev)
  if (d === 'IN') return 'flash-in'
  if (d === 'OUT') return 'flash-out'
  return ''
}

function maskName(name, addr) {
  if (store.hideAddresses) return '••••••••••••'
  if (name) return name.length > 13 ? name.slice(0, 13) + '…' : name
  return shortAddr(addr)
}

function walletDisplay(name, addr) {
  if (store.hideAddresses) return '••••••••••••'
  const w = store.wallets.find(ww => ww.id === addr)
  const owner = w?.owner
  const base = name || shortAddr(addr)
  const full = owner ? `${base} - ${owner}` : base
  return full.length > 20 ? full.slice(0, 19) + '…' : full
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


function shortTx(id) {
  if (!id) return '—'
  if (store.hideAddresses) return '••••••'
  return id.length > 5 ? `${id.slice(0, 5)}…` : id
}
function shortTick(tick) {
  if (tick == null) return '—'
  const s = String(tick)
  return s.length > 5 ? `${s.slice(0, 5)}…` : s
}

// Prefer the real TX digest (explorer id) over the internal log id.
// For archiver-sourced records, log_digest === id; for event-log-sourced
// records, log_digest holds the explorer-visible txId while id is a short logId.
function txId(ev) {
  return ev.log_digest || ev.id
}

// Qubic txIds are exactly 60 lowercase letters a–z. The explorer's
// /network/tx/... route only works with those — for shorter ids
// (e.g. the 16-hex logDigest from getEventLogs) we hide the tx-icon
// and keep the separate tick-explorer link as the reliable fallback.
function isRealTxId(id) {
  return typeof id === 'string' && /^[a-z]{60}$/.test(id)
}

function walletLabel(addr) {
  const w = store.wallets.find(wallet => wallet.id === addr)
  return w ? w.label : null
}

function isOwnWallet(addr) {
  return !!store.wallets.find(w => w.id === addr)
}

function sign(ev) {
  const dir = direction(ev)
  if (dir === 'IN') return '+'
  if (dir === 'OUT') return '−'
  if (dir === 'INTERNAL') return ev.wallet_id === ev.source_address ? '−' : '+'
  return ''
}

function signClass(ev) {
  const s = sign(ev)
  if (s === '+') return 'text-green-400'
  if (s === '−') return 'text-red-400'
  return 'text-gray-400'
}

function counterpart(ev) {
  const dir = direction(ev)
  if (dir === 'IN')  return { addr: ev.source_address,  name: ev.source_name || walletLabel(ev.source_address) }
  if (dir === 'OUT') return { addr: ev.destination_addr, name: ev.destination_name || walletLabel(ev.destination_addr) }
  if (dir === 'INTERNAL') {
    const otherAddr = ev.wallet_id === ev.source_address ? ev.destination_addr : ev.source_address
    return { addr: otherAddr, name: walletLabel(otherAddr) }
  }
  return { addr: ev.source_address, name: ev.source_name }
}
</script>

<template>
  <div class="card overflow-hidden">
    <div v-if="title" class="px-3 pt-3 pb-1 text-sm text-gray-500 uppercase tracking-wide">{{ title }}</div>
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
            <span v-else-if="direction(ev) === 'INTERNAL' && sign(ev) === '−'" class="text-yellow-400 text-xs font-bold">⇄ INT</span>
            <span v-else-if="direction(ev) === 'INTERNAL' && sign(ev) === '+'" class="text-yellow-400 text-xs font-bold">⇄ INT</span>
            <span v-else-if="direction(ev) === 'INTERNAL'" class="text-gray-400 text-xs font-bold">⇄ INT</span>
            <span v-else class="text-gray-500 text-xs">—</span>
          </div>
          <!-- Main info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span :class="['font-mono text-xs font-medium', signClass(ev)]"><span class="mr-0.5">{{ sign(ev) }}</span>{{ Number(ev.amount_qubic || 0).toLocaleString('de-DE') }} QU</span>
              <span class="text-xs text-gray-400">{{ fmtValue(ev) }}</span>
            </div>
            <div class="text-xs text-gray-500 mt-0.5">{{ fmtDate(ev.timestamp) }} · Ep. {{ ev.epoch ?? '—' }}</div>
            <!-- Counterpart address -->
            <div v-if="counterpart(ev).addr" class="flex items-center gap-1 mt-1">
              <span :class="['text-xs font-mono truncate', isOwnWallet(counterpart(ev).addr) ? 'text-violet-300' : 'text-gray-400']">
                {{ walletDisplay(counterpart(ev).name, counterpart(ev).addr) }}
              </span>
              <button v-if="!store.hideAddresses" @click="copyAddress(counterpart(ev).addr)"
                      class="icon-btn" :title="t('assets.copy')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
              <a :href="explorerUrl(counterpart(ev).addr)" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
            <!-- TxId -->
            <div class="flex items-start gap-1 mt-1 min-w-0">
              <span class="text-xs text-gray-500 font-mono break-all" :title="store.hideAddresses ? '' : txId(ev)">{{ shortTx(txId(ev)) }}</span>
              <button v-if="!store.hideAddresses" @click="copyAddress(txId(ev))"
                      class="icon-btn" :title="t('event.copy_txid')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
              <a :href="txUrl(txId(ev))" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
            <!-- Tick -->
            <div v-if="ev.tick_number" class="flex items-center gap-1 mt-0.5">
              <span class="text-xs text-gray-500 font-mono" :title="ev.tick_number">{{ t('event.tick') }}: {{ shortTick(ev.tick_number) }}</span>
              <button @click="copyAddress(String(ev.tick_number))"
                      class="icon-btn" :title="t('event.copy_tick')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
              <a :href="tickUrl(ev.tick_number)" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
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
        <table class="table-std">
          <thead class="thead-std">
            <tr>
              <th class="text-left px-3 py-2.5">{{ t('event.date') }}</th>
              <th class="text-left px-3 py-2.5">{{ t('event.epoch') }}</th>
              <th class="text-left px-3 py-2.5">{{ t('event.direction') }}</th>
              <th class="text-right px-3 py-2.5">{{ t('event.amount') }}</th>
              <th class="text-right px-3 py-2.5 hidden lg:table-cell whitespace-nowrap">{{ t('event.rate') }} {{ store.currency }}</th>
              <th class="text-right px-3 py-2.5 whitespace-nowrap">{{ t('event.value_col') }} {{ store.currency }}</th>
              <th class="text-right px-3 py-2.5">{{ t('event.source') }}</th>
              <th class="text-right px-3 py-2.5">{{ t('event.destination') }}</th>
              <th class="text-left px-3 py-2.5">{{ t('event.txid') }}</th>
              <th class="text-left px-3 py-2.5">{{ t('event.tick') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!events.length">
              <td colspan="9" class="text-center p-8 text-gray-500">{{ t('event.none') }}</td>
            </tr>
            <tr v-for="ev in events" :key="ev.id"
                :class="[
                  store.newEventIds.includes(ev.id) ? animClass : '',
                  store.newEventIds.includes(ev.id) ? flashClass(ev) : '',
                  'tr-row'
                ]">
              <td class="px-3 py-2.5 text-gray-400 whitespace-nowrap">{{ fmtDate(ev.timestamp) }}</td>
              <td class="px-3 py-2.5 text-gray-400 font-mono">{{ ev.epoch ?? '—' }}</td>
              <td class="px-3 py-2.5">
                <span v-if="direction(ev) === 'IN'"       class="text-green-400 font-medium">▲ IN</span>
                <span v-else-if="direction(ev) === 'OUT'" class="text-red-400 font-medium">▼ OUT</span>
                <span v-else-if="direction(ev) === 'INTERNAL' && sign(ev) === '−'" class="text-yellow-400 font-medium">⇄ INT</span>
                <span v-else-if="direction(ev) === 'INTERNAL' && sign(ev) === '+'" class="text-yellow-400 font-medium">⇄ INT</span>
                <span v-else-if="direction(ev) === 'INTERNAL'" class="text-gray-400">⇄ INT</span>
                <span v-else class="text-gray-500">—</span>
              </td>
              <td :class="['px-3 py-2.5 font-mono text-right whitespace-nowrap', signClass(ev)]"><span class="mr-0.5">{{ sign(ev) }}</span>{{ Number(ev.amount_qubic || 0).toLocaleString('de-DE') }} QU</td>
              <td class="px-3 py-2.5 font-mono text-gray-400 text-right hidden lg:table-cell whitespace-nowrap">{{ fmtRate(ev) }}</td>
              <td class="px-3 py-2.5 font-mono text-right whitespace-nowrap">{{ fmtValue(ev) }}</td>
              <!-- Source -->
              <td class="px-3 py-2.5">
                <div v-if="ev.source_address" class="flex items-center justify-end gap-2 font-mono text-xs text-gray-400">
                  <span :class="isOwnWallet(ev.source_address) ? 'text-violet-300' : ''" :title="store.hideAddresses ? '' : ev.source_address">
                    {{ walletDisplay(ev.source_name || walletLabel(ev.source_address), ev.source_address) }}
                  </span>
                  <button v-if="!store.hideAddresses" @click="copyAddress(ev.source_address)"
                          class="icon-btn" :title="t('assets.copy')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <a :href="explorerUrl(ev.source_address)" target="_blank" rel="noopener"
                     class="icon-btn" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <span v-else class="text-gray-500">—</span>
              </td>
              <!-- Destination -->
              <td class="px-3 py-2.5">
                <div v-if="ev.destination_addr" class="flex items-center justify-end gap-2 font-mono text-xs text-gray-400">
                  <span :class="isOwnWallet(ev.destination_addr) ? 'text-violet-300' : ''" :title="store.hideAddresses ? '' : ev.destination_addr">
                    {{ walletDisplay(ev.destination_name || walletLabel(ev.destination_addr), ev.destination_addr) }}
                  </span>
                  <button v-if="!store.hideAddresses" @click="copyAddress(ev.destination_addr)"
                          class="icon-btn" :title="t('assets.copy')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <a :href="explorerUrl(ev.destination_addr)" target="_blank" rel="noopener"
                     class="icon-btn" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <span v-else class="text-gray-500">—</span>
              </td>
              <!-- TxId -->
              <td class="px-3 py-2.5">
                <div class="flex items-start gap-2 font-mono text-xs text-gray-400 min-w-0">
                  <span class="break-all" :title="store.hideAddresses ? '' : txId(ev)">{{ shortTx(txId(ev)) }}</span>
                  <button v-if="!store.hideAddresses" @click="copyAddress(txId(ev))"
                          class="icon-btn" :title="t('event.copy_txid')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <a :href="txUrl(txId(ev))" target="_blank" rel="noopener"
                     class="icon-btn" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
              </td>
              <!-- Tick -->
              <td class="px-3 py-2.5">
                <div v-if="ev.tick_number" class="flex items-center gap-2 font-mono text-xs text-gray-400">
                  <span :title="ev.tick_number">{{ shortTick(ev.tick_number) }}</span>
                  <button @click="copyAddress(String(ev.tick_number))"
                          class="icon-btn" :title="t('event.copy_tick')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <a :href="tickUrl(ev.tick_number)" target="_blank" rel="noopener"
                     class="icon-btn" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
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
