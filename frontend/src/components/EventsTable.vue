<script setup>
import { computed, ref } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import { useQubicUtils } from '../composables/useQubicUtils'
import { api } from '../api'

const props = defineProps({
  events:   { type: Array, required: true },
  loading:  { type: Boolean, default: false },
  title:    { type: String, default: null },
  readonly: { type: Boolean, default: false },
})

const editingNoteId = ref(null)
const noteInput     = ref('')
const noteSaving    = ref(false)

function noteKey(ev) { return `${ev.id}__${ev.wallet_id}` }

function startEditNote(ev) {
  editingNoteId.value = noteKey(ev)
  noteInput.value = ev.note || ''
}

function cancelEditNote() {
  editingNoteId.value = null
  noteInput.value = ''
}

async function saveNote(ev) {
  noteSaving.value = true
  try {
    await api.events.updateNote(ev.id, ev.wallet_id, noteInput.value)
    ev.note = noteInput.value || null
    editingNoteId.value = null
  } finally {
    noteSaving.value = false
  }
}

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

function flashClass(ev) {
  if (ev._dir === 'IN') return 'flash-in'
  if (ev._dir === 'OUT') return 'flash-out'
  return ''
}

function getWallet(addr) {
  return store.wallets.find(w => w.id === addr) ?? null
}

function walletLabel(addr) {
  return getWallet(addr)?.label ?? null
}

function isOwnWallet(addr) {
  return ownedIds.value.has(addr)
}

function walletDisplay(name, addr) {
  if (store.hideAddresses) return '••••••••••••'
  const w = getWallet(addr)
  const owner = w?.owner
  const base = name || shortAddr(addr)
  const full = owner ? `${base} - ${owner}` : base
  return full.length > 20 ? full.slice(0, 19) + '…' : full
}

function fmtValue(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_usd_rate : ev.qubic_eur_rate
  if (!ev.amount_qubic || !rate) return '—'
  return (ev.amount_qubic * rate).toFixed(2) + (isUsd ? '$' : '€')
}

function fmtRate(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_usd_rate : ev.qubic_eur_rate
  if (!rate) return '—'
  return rate.toFixed(10).replace(/\.?0+$/, '') + (isUsd ? '$' : '€')
}

function fmtValueAlt(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_eur_rate : ev.qubic_usd_rate
  if (!ev.amount_qubic || !rate) return undefined
  return (ev.amount_qubic * rate).toFixed(2) + (isUsd ? '€' : '$')
}

function fmtRateAlt(ev) {
  const isUsd = store.currency === 'USD'
  const rate = isUsd ? ev.qubic_eur_rate : ev.qubic_usd_rate
  if (!rate) return undefined
  return rate.toFixed(10).replace(/\.?0+$/, '') + (isUsd ? '€' : '$')
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

function txId(ev) {
  const id = ev.log_digest || ev.id
  return (typeof id === 'string' && /^[a-z]{60}$/.test(id)) ? id : null
}

function signClass(ev) {
  if (ev._sign === '+') return 'text-green-400'
  if (ev._sign === '−') return 'text-red-400'
  return 'text-gray-400'
}

function counterpart(ev) {
  if (ev._dir === 'IN')  return { addr: ev.source_address,  name: ev.source_name || walletLabel(ev.source_address) }
  if (ev._dir === 'OUT') return { addr: ev.destination_addr, name: ev.destination_name || walletLabel(ev.destination_addr) }
  if (ev._dir === 'INTERNAL') {
    const otherAddr = ev.wallet_id === ev.source_address ? ev.destination_addr : ev.source_address
    return { addr: otherAddr, name: walletLabel(otherAddr) }
  }
  return { addr: ev.source_address, name: ev.source_name }
}

const processedEvents = computed(() => props.events.map(ev => {
  const _dir = ev.is_internal ? 'INTERNAL'
    : ownedIds.value.has(ev.destination_addr) ? 'IN'
    : ownedIds.value.has(ev.source_address) ? 'OUT'
    : '—'
  const _sign = _dir === 'IN' ? '+'
    : _dir === 'OUT' ? '−'
    : _dir === 'INTERNAL' ? (ev.wallet_id === ev.source_address ? '−' : '+')
    : ''
  return { ...ev, _dir, _sign }
}))
</script>

<template>
  <div class="card overflow-hidden">
    <div v-if="title" class="px-3 pt-3 pb-1 text-sm text-gray-500 uppercase tracking-wide">{{ title }}</div>
    <div v-if="loading" class="p-8 text-center text-gray-500 text-xs">{{ t('common.loading') }}</div>

    <template v-else>
      <!-- Mobile: card list -->
      <div class="sm:hidden divide-y divide-qubic-border/40">
        <div v-if="!events.length" class="p-6 text-center text-gray-500 text-xs">{{ t('event.none') }}</div>
        <div v-for="ev in processedEvents" :key="ev.id"
             :class="[
               store.newEventIds.includes(ev.id) ? animClass : '',
               store.newEventIds.includes(ev.id) ? flashClass(ev) : '',
               'p-3 flex items-start gap-3'
             ]">
          <!-- Direction badge -->
          <div class="flex-shrink-0 mt-0.5">
            <span v-if="ev._dir === 'IN'"       class="text-green-400 text-xs font-bold">▲ IN</span>
            <span v-else-if="ev._dir === 'OUT'" class="text-red-400 text-xs font-bold">▼ OUT</span>
            <span v-else-if="ev._dir === 'INTERNAL' && ev._sign === '−'" class="text-yellow-400 text-xs font-bold">⇄ INT</span>
            <span v-else-if="ev._dir === 'INTERNAL' && ev._sign === '+'" class="text-yellow-400 text-xs font-bold">⇄ INT</span>
            <span v-else-if="ev._dir === 'INTERNAL'" class="text-gray-400 text-xs font-bold">⇄ INT</span>
            <span v-else class="text-gray-500 text-xs">—</span>
          </div>
          <!-- Main info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span :class="['font-mono text-xs font-medium', signClass(ev)]"><span class="mr-0.5">{{ ev._sign }}</span>{{ Number(ev.amount_qubic || 0).toLocaleString(store.locale) }} QU</span>
              <span class="text-xs text-gray-400" :title="fmtValueAlt(ev)">{{ fmtValue(ev) }}</span>
            </div>
            <div class="text-xs text-gray-500 mt-0.5">{{ fmtDate(ev.timestamp) }} · Ep. {{ ev.epoch ?? '—' }}</div>
            <!-- Counterpart address -->
            <div v-if="counterpart(ev).addr" class="flex items-center gap-1 mt-1">
              <span :class="['text-xs font-mono truncate', isOwnWallet(counterpart(ev).addr) ? 'text-violet-300' : 'text-gray-400', !store.hideAddresses && 'cursor-pointer hover:opacity-80']"
                    :title="!store.hideAddresses ? t('assets.copy') : ''"
                    @click="!store.hideAddresses && copyAddress(counterpart(ev).addr)">
                {{ walletDisplay(counterpart(ev).name, counterpart(ev).addr) }}
              </span>
              <a :href="explorerUrl(counterpart(ev).addr)" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
            <!-- TxId -->
            <div v-if="txId(ev)" class="flex items-start gap-1 mt-1 min-w-0">
              <span :class="['text-xs text-gray-500 font-mono break-all', !store.hideAddresses && 'cursor-pointer hover:text-gray-300']"
                    :title="store.hideAddresses ? '' : t('event.copy_txid')"
                    @click="!store.hideAddresses && copyAddress(txId(ev))">
                {{ shortTx(txId(ev)) }}
              </span>
              <a :href="txUrl(txId(ev))" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
            <!-- Tick -->
            <div v-if="ev.tick_number" class="flex items-center gap-1 mt-0.5">
              <span class="text-xs text-gray-500 font-mono cursor-pointer hover:text-gray-300"
                    :title="t('event.copy_tick')"
                    @click="copyAddress(String(ev.tick_number))">
                {{ t('event.tick') }}: {{ shortTick(ev.tick_number) }}
              </span>
              <a :href="tickUrl(ev.tick_number)" target="_blank" rel="noopener"
                 class="icon-btn" :title="t('assets.explorer')">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            </div>
            <!-- Note (mobile) -->
            <div v-if="!props.readonly" class="mt-1.5">
              <template v-if="editingNoteId === noteKey(ev)">
                <div class="flex items-center gap-1.5">
                  <input v-model="noteInput"
                         class="input text-xs py-0.5 px-2 flex-1 min-w-0"
                         :placeholder="t('event.note_placeholder')"
                         @keyup.enter="saveNote(ev)"
                         @keyup.esc="cancelEditNote" />
                  <button :disabled="noteSaving" @click="saveNote(ev)"
                          class="icon-btn text-green-400 hover:text-green-300" :title="t('event.note_save')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </button>
                  <button @click="cancelEditNote"
                          class="icon-btn text-red-400 hover:text-red-300" :title="t('event.note_cancel')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </div>
              </template>
              <template v-else>
                <div class="flex items-center gap-1.5">
                  <span v-if="ev.note" class="text-xs text-gray-300 break-all">{{ ev.note }}</span>
                  <button class="icon-btn" :title="t('event.note')" @click.stop="startEditNote(ev)">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                  </button>
                </div>
              </template>
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
              <th class="text-right px-3 py-2.5 whitespace-nowrap">{{ t('event.amount') }} / {{ t('event.value_col') }}</th>
              <th class="text-right px-3 py-2.5 whitespace-nowrap">{{ t('event.rate') }}</th>
              <th class="text-right px-3 py-2.5">{{ t('event.source') }} / {{ t('event.destination') }}</th>
              <th class="text-right px-3 py-2.5">{{ t('event.txid') }} / {{ t('event.tick') }}</th>
              <th v-if="!props.readonly" class="text-left px-3 py-2.5">{{ t('event.note') }}</th>
              <th v-if="!props.readonly" class="px-3 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!events.length">
              <td colspan="9" class="text-center p-8 text-gray-500">{{ t('event.none') }}</td>
            </tr>
            <tr v-for="ev in processedEvents" :key="ev.id"
                :class="[
                  store.newEventIds.includes(ev.id) ? animClass : '',
                  store.newEventIds.includes(ev.id) ? flashClass(ev) : '',
                  'tr-row'
                ]">
              <td class="px-3 py-2.5 text-gray-400 whitespace-nowrap">{{ fmtDate(ev.timestamp) }}</td>
              <td class="px-3 py-2.5 text-gray-400 font-mono">{{ ev.epoch ?? '—' }}</td>
              <td class="px-3 py-2.5">
                <span v-if="ev._dir === 'IN'"       class="text-green-400 font-medium">▲ IN</span>
                <span v-else-if="ev._dir === 'OUT'" class="text-red-400 font-medium">▼ OUT</span>
                <span v-else-if="ev._dir === 'INTERNAL' && ev._sign === '−'" class="text-yellow-400 font-medium">⇄ INT</span>
                <span v-else-if="ev._dir === 'INTERNAL' && ev._sign === '+'" class="text-yellow-400 font-medium">⇄ INT</span>
                <span v-else-if="ev._dir === 'INTERNAL'" class="text-gray-400">⇄ INT</span>
                <span v-else class="text-gray-500">—</span>
              </td>
              <!-- Betrag / Wert (kombiniert) -->
              <td class="px-3 py-2.5 text-right">
                <div :class="['font-mono whitespace-nowrap', signClass(ev)]">
                  <span class="mr-0.5">{{ ev._sign }}</span>{{ Number(ev.amount_qubic || 0).toLocaleString(store.locale) }} QU
                </div>
                <div class="font-mono whitespace-nowrap text-xs">{{ fmtValue(ev) }}</div>
              </td>
              <!-- Kurs: gewählte Währung zuerst -->
              <td class="px-3 py-2.5 text-right font-mono text-xs">
                <template v-if="store.currency === 'USD'">
                  <div class="whitespace-nowrap">{{ ev.qubic_usd_rate ? ev.qubic_usd_rate.toFixed(10).replace(/\.?0+$/, '') + '$' : '—' }}</div>
                  <div class="whitespace-nowrap text-gray-500">{{ ev.qubic_eur_rate ? ev.qubic_eur_rate.toFixed(10).replace(/\.?0+$/, '') + '€' : '—' }}</div>
                </template>
                <template v-else>
                  <div class="whitespace-nowrap">{{ ev.qubic_eur_rate ? ev.qubic_eur_rate.toFixed(10).replace(/\.?0+$/, '') + '€' : '—' }}</div>
                  <div class="whitespace-nowrap text-gray-500">{{ ev.qubic_usd_rate ? ev.qubic_usd_rate.toFixed(10).replace(/\.?0+$/, '') + '$' : '—' }}</div>
                </template>
              </td>
              <!-- Sender / Empfänger (kombiniert) -->
              <td class="px-3 py-2.5">
                <div class="flex items-center justify-end gap-1.5 font-mono text-xs min-w-0">
                  <span v-if="ev.source_address"
                        :class="['truncate', isOwnWallet(ev.source_address) ? 'text-violet-300' : 'text-gray-400', !store.hideAddresses && 'cursor-pointer hover:opacity-80']"
                        :title="store.hideAddresses ? '' : ev.source_address"
                        @click="!store.hideAddresses && copyAddress(ev.source_address)">
                    {{ walletDisplay(ev.source_name || walletLabel(ev.source_address), ev.source_address) }}
                  </span>
                  <span v-else class="text-gray-500">—</span>
                  <a v-if="ev.source_address" :href="explorerUrl(ev.source_address)" target="_blank" rel="noopener"
                     class="icon-btn shrink-0" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <div class="flex items-center justify-end gap-1.5 font-mono text-xs min-w-0 mt-0.5">
                  <span v-if="ev.destination_addr"
                        :class="['truncate', isOwnWallet(ev.destination_addr) ? 'text-violet-300' : 'text-gray-400', !store.hideAddresses && 'cursor-pointer hover:opacity-80']"
                        :title="store.hideAddresses ? '' : ev.destination_addr"
                        @click="!store.hideAddresses && copyAddress(ev.destination_addr)">
                    {{ walletDisplay(ev.destination_name || walletLabel(ev.destination_addr), ev.destination_addr) }}
                  </span>
                  <span v-else class="text-gray-500">—</span>
                  <a v-if="ev.destination_addr" :href="explorerUrl(ev.destination_addr)" target="_blank" rel="noopener"
                     class="icon-btn shrink-0" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
              </td>
              <!-- TXID / Tick (kombiniert) -->
              <td class="px-3 py-2.5">
                <div class="flex items-center justify-end gap-1.5 font-mono text-xs text-gray-400">
                  <span v-if="txId(ev)"
                        :class="['whitespace-nowrap', !store.hideAddresses && 'cursor-pointer hover:text-gray-200']"
                        :title="store.hideAddresses ? '' : txId(ev)"
                        @click="!store.hideAddresses && copyAddress(txId(ev))">
                    {{ shortTx(txId(ev)) }}
                  </span>
                  <span v-else class="text-gray-500">—</span>
                  <a v-if="txId(ev)" :href="txUrl(txId(ev))" target="_blank" rel="noopener"
                     class="icon-btn shrink-0" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
                <div class="flex items-center justify-end gap-1.5 font-mono text-xs text-gray-400 mt-0.5">
                  <span v-if="ev.tick_number"
                        class="whitespace-nowrap cursor-pointer hover:text-gray-200"
                        :title="String(ev.tick_number)"
                        @click="copyAddress(String(ev.tick_number))">
                    {{ shortTick(ev.tick_number) }}
                  </span>
                  <span v-else class="text-gray-500">—</span>
                  <a v-if="ev.tick_number" :href="tickUrl(ev.tick_number)" target="_blank" rel="noopener"
                     class="icon-btn shrink-0" :title="t('assets.explorer')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                </div>
              </td>
              <!-- Note -->
              <td v-if="!props.readonly" class="px-3 py-2.5 min-w-[180px]">
                <template v-if="editingNoteId === noteKey(ev)">
                  <input v-model="noteInput"
                         class="input text-xs py-0.5 px-2 w-full"
                         :placeholder="t('event.note_placeholder')"
                         @keyup.enter="saveNote(ev)"
                         @keyup.esc="cancelEditNote" />
                </template>
                <template v-else>
                  <span v-if="ev.note" class="text-xs text-gray-300 break-words block" :title="ev.note">{{ ev.note }}</span>
                  <span v-else class="text-xs text-gray-600">—</span>
                </template>
              </td>
              <!-- Note actions -->
              <td v-if="!props.readonly" class="px-3 py-2.5 whitespace-nowrap">
                <template v-if="editingNoteId === noteKey(ev)">
                  <div class="flex items-center gap-1.5">
                    <button :disabled="noteSaving" @click="saveNote(ev)"
                            class="icon-btn text-green-400 hover:text-green-300" :title="t('event.note_save')">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    </button>
                    <button @click="cancelEditNote"
                            class="icon-btn text-red-400 hover:text-red-300" :title="t('event.note_cancel')">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </div>
                </template>
                <template v-else>
                  <button @click.stop="startEditNote(ev)"
                          class="icon-btn" :title="t('event.note')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                  </button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
