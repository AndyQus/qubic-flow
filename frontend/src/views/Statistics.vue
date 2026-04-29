<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import { useAppStore } from '../stores/app'
import { useQubicUtils } from '../composables/useQubicUtils'
import { Line, Bar } from 'vue-chartjs'
import WalletFilter from '../components/WalletFilter.vue'
import PageLoader from '../components/PageLoader.vue'
import PageHeader from '../components/PageHeader.vue'
import OwnerIcon from '../components/OwnerIcon.vue'
import InfoLabel from '../components/InfoLabel.vue'
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, Filler,
} from 'chart.js'

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, CategoryScale, LinearScale, PointElement, Filler)

const { t } = useTranslation()
const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { maskLabel } = useQubicUtils()

const periodIcons = {
  hour:  'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  day:   'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
  epoch: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  month: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  year:  'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

const periodColors = {
  hour:  'text-sky-400',
  day:   'text-amber-400',
  epoch: 'text-violet-400',
  month: 'text-emerald-400',
  year:  'text-rose-400',
}

const currencySymbol    = computed(() => store.currency === 'USD' ? '$' : '€')
const altCurrencySymbol = computed(() => store.currency === 'USD' ? '€' : '$')
const volumeKey         = computed(() => store.currency === 'USD' ? 'volume_usd' : 'volume_eur')
const altVolumeKey      = computed(() => store.currency === 'USD' ? 'volume_eur' : 'volume_usd')
const inFiatKey         = computed(() => store.currency === 'USD' ? 'in_usd' : 'in_eur')
const altInFiatKey      = computed(() => store.currency === 'USD' ? 'in_eur' : 'in_usd')
const outFiatKey        = computed(() => store.currency === 'USD' ? 'out_usd' : 'out_eur')
const altOutFiatKey     = computed(() => store.currency === 'USD' ? 'out_eur' : 'out_usd')
const stats          = ref(null)
const snaps          = ref([])
const history        = ref([])
const epochsData     = ref([])
const mode           = ref('count')
const selectedWallets = ref([])
const selectedEpochWallets = ref([])
const selectedFunction = ref(null)
const loading = ref(true)

const FUNCTION_COLORS = [
  { active: 'bg-sky-500/20 border-sky-400 text-sky-300',       idle: 'text-gray-400 hover:bg-sky-500/10 hover:border-sky-400/60 hover:text-sky-300'      },
  { active: 'bg-amber-500/20 border-amber-400 text-amber-300',  idle: 'text-gray-400 hover:bg-amber-500/10 hover:border-amber-400/60 hover:text-amber-300'  },
  { active: 'bg-violet-500/20 border-violet-400 text-violet-300', idle: 'text-gray-400 hover:bg-violet-500/10 hover:border-violet-400/60 hover:text-violet-300' },
  { active: 'bg-rose-500/20 border-rose-400 text-rose-300',     idle: 'text-gray-400 hover:bg-rose-500/10 hover:border-rose-400/60 hover:text-rose-300'     },
  { active: 'bg-emerald-500/20 border-emerald-400 text-emerald-300', idle: 'text-gray-400 hover:bg-emerald-500/10 hover:border-emerald-400/60 hover:text-emerald-300' },
  { active: 'bg-orange-500/20 border-orange-400 text-orange-300', idle: 'text-gray-400 hover:bg-orange-500/10 hover:border-orange-400/60 hover:text-orange-300' },
  { active: 'bg-pink-500/20 border-pink-400 text-pink-300',     idle: 'text-gray-400 hover:bg-pink-500/10 hover:border-pink-400/60 hover:text-pink-300'     },
]

function functionBtnClass(fn, i) {
  const c = FUNCTION_COLORS[i % FUNCTION_COLORS.length]
  return ['btn-ghost text-xs py-1 px-3 transition-colors', selectedFunction.value === fn ? c.active : c.idle]
}

function toggleFunction(fn) {
  selectedFunction.value = selectedFunction.value === fn ? null : fn
}

// Tabs + epoch selection, URL-synced (?tab=epochs|overview&epoch=168&ext=1)
const activeTab = ref(route.query.tab === 'overview' ? 'overview' : 'epochs')
const selectedEpoch = ref(route.query.epoch != null ? Number(route.query.epoch) : null)
// `extended` is a computed directly from the route — avoids stale ref-watch timing
const extended = computed(() => route.query.ext === '1')

watch(() => route.query, (q) => {
  activeTab.value = q.tab === 'overview' ? 'overview' : 'epochs'
  selectedEpoch.value = q.epoch != null ? Number(q.epoch) : null
})

function setActiveTab(tab) {
  const q = {}
  if (tab === 'overview') q.tab = 'overview'
  router.push({ path: '/stats', query: q })
}

function setSelectedEpoch(epoch) {
  const q = { ...route.query }
  if (epoch != null) q.epoch = String(epoch)
  else delete q.epoch
  router.push({ path: '/stats', query: q })
}

function toggleExtended() {
  const q = { ...route.query }
  if (!extended.value) q.ext = '1'
  else delete q.ext
  router.push({ path: '/stats', query: q })
}

async function loadStats() {
  loading.value = true
  try {
    let ids = selectedWallets.value
    if (selectedFunction.value) {
      const fnIds = new Set(store.wallets.filter(w => w.function === selectedFunction.value).map(w => w.id))
      ids = ids.length ? ids.filter(id => fnIds.has(id)) : [...fnIds]
    }
    ;[stats.value, snaps.value, history.value, epochsData.value] = await Promise.all([
      api.stats.current(ids),
      ids.length ? Promise.resolve([]) : api.stats.snapshots(),
      api.stats.history('week', ids),
      api.stats.epochs(),
    ])
  } finally { loading.value = false }
}

watch(selectedWallets, loadStats, { deep: true })
watch(selectedFunction, loadStats)
onMounted(loadStats)

// ── Formatierung ────────────────────────────────────────────────
function fmt(n)    { return n == null ? '—' : Number(n).toLocaleString(store.locale) }
function fmtCurrency(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + currencySymbol.value
}

function fmtCurrencyAlt(n) {
  if (n == null) return undefined
  return Number(n).toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + altCurrencySymbol.value
}

// ── Trend-Pfeil ─────────────────────────────────────────────────
function trend(cur, prev) {
  if (!prev || prev === 0) return null
  const pct = ((cur - prev) / prev) * 100
  return { pct: Math.abs(pct).toFixed(1), up: pct >= 0 }
}

// ── Perioden-Karten ─────────────────────────────────────────────
const periods = computed(() => {
  if (!stats.value) return []
  return ['hour', 'day', 'epoch', 'month', 'year'].map(k => {
    const cur  = stats.value[k].current
    const prev = stats.value[k].previous
    return { key: k, label: t(`stats.${k}`), cur, prev, trend: trend(cur.count, prev.count) }
  })
})

// ── Merge Snapshots + Live-History ──────────────────────────────
const mergedData = computed(() => {
  const snapMap = new Map()
  for (const s of snaps.value) {
    const key = `${s.year}-${String(s.week).padStart(2, '0')}`
    snapMap.set(key, { ...s, source: 'snapshot' })
  }

  const merged = new Map(snapMap)
  for (const h of history.value) {
    const key = `${h.year}-${String(h.week).padStart(2, '0')}`
    if (!merged.has(key)) {
      merged.set(key, { ...h, source: 'live' })
    }
  }

  return [...merged.values()].sort((a, b) => {
    if (a.year !== b.year) return a.year - b.year
    return (a.week || 0) - (b.week || 0)
  })
})

const totals = computed(() => {
  if (!mergedData.value.length) return null
  return mergedData.value.reduce((acc, s) => ({
    tx:     acc.tx     + (s.tx_count     || 0),
    events: acc.events + (s.event_count  || 0),
    qubic:  acc.qubic  + (s.volume_qubic || 0),
    eur:    acc.eur    + (s[volumeKey.value] || 0),
  }), { tx: 0, events: 0, qubic: 0, eur: 0 })
})

const hasData = computed(() => mergedData.value.length > 0)

const lineData = computed(() => {
  const items  = mergedData.value
  const labels = items.map(s => {
    const live = s.source === 'live' ? ' ●' : ''
    return `KW${s.week}/${s.year}${live}`
  })

  if (mode.value === 'count') {
    return {
      labels,
      datasets: [
        { label: 'Events', data: items.map(s => s.event_count || 0),
          borderColor: '#2dd4bf', backgroundColor: 'rgba(45,212,191,0.1)', fill: true, tension: 0.4,
          segment: { borderColor: ctx => items[ctx.p1DataIndex]?.source === 'live' ? '#2dd4bf88' : '#2dd4bf' } },
        { label: 'TX',     data: items.map(s => s.tx_count    || 0),
          borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)',  fill: true, tension: 0.4,
          segment: { borderColor: ctx => items[ctx.p1DataIndex]?.source === 'live' ? '#f59e0b88' : '#f59e0b' } },
      ],
    }
  }
  if (mode.value === 'volume_fiat') {
    return {
      labels,
      datasets: [
        { label: `${t('stats.volume')} ${store.currency}`, data: items.map(s => +((s[volumeKey.value]) || 0).toFixed(2)),
          borderColor: '#2dd4bf', backgroundColor: 'rgba(45,212,191,0.1)', fill: true, tension: 0.4 },
      ],
    }
  }
  return {
    labels,
    datasets: [
      { label: t('stats.volume_qubic'), data: items.map(s => s.volume_qubic || 0),
        borderColor: '#2dd4bf', backgroundColor: 'rgba(45,212,191,0.1)', fill: true, tension: 0.4 },
    ],
  }
})

const barData = computed(() => {
  const items = mergedData.value.slice(-12)
  return {
    labels: items.map(s => `KW${s.week}`),
    datasets: [
      { label: 'Events', data: items.map(s => s.event_count || 0),
        backgroundColor: items.map(s => s.source === 'live' ? 'rgba(45,212,191,0.35)' : 'rgba(45,212,191,0.65)'), borderRadius: 4 },
      { label: 'TX',     data: items.map(s => s.tx_count    || 0),
        backgroundColor: items.map(s => s.source === 'live' ? 'rgba(245,158,11,0.35)'  : 'rgba(245,158,11,0.65)'),  borderRadius: 4 },
    ],
  }
})

const chartOptions = computed(() => {
  const isLight = store.theme === 'light'
  const labelColor  = isLight ? '#374151' : '#e5e7eb'
  const tickColor   = isLight ? '#4b5563' : '#9ca3af'
  const gridColor   = isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.05)'
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: labelColor, boxWidth: 12 } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: { ticks: { color: tickColor, maxRotation: 45 }, grid: { color: gridColor } },
      y: { ticks: { color: tickColor }, grid: { color: gridColor }, beginAtZero: true },
    },
  }
})

// ── Epochen-Tab ─────────────────────────────────────────────────
const walletMap = computed(() => {
  const m = new Map()
  for (const w of store.wallets) m.set(w.id, w)
  return m
})

const availableEpochs = computed(() => epochsData.value.map(e => e.epoch))

const activeEpoch = computed(() => {
  if (!epochsData.value.length) return null
  if (selectedEpoch.value != null && availableEpochs.value.includes(selectedEpoch.value)) {
    return selectedEpoch.value
  }
  return epochsData.value[0].epoch
})

const currentEpochGroup = computed(() => {
  if (activeEpoch.value == null) return null
  return epochsData.value.find(e => e.epoch === activeEpoch.value) || null
})

// Wallets with activity (in or out) in the selected epoch — feed this list to WalletFilter
const epochActiveWallets = computed(() => {
  const g = currentEpochGroup.value
  if (!g) return []
  return g.wallets
    .filter(r => r.in_qubic > 0 || r.out_qubic > 0)
    .map(r => walletMap.value.get(r.wallet_id))
    .filter(w => w && w.deleted_at == null)
})

// Reset epoch-specific wallet selection + function when the epoch or tab changes
watch(activeEpoch, () => { selectedEpochWallets.value = []; selectedFunction.value = null })
watch(activeTab,   () => { selectedFunction.value = null })

const availableFunctions = computed(() => {
  const walletList = activeTab.value === 'epochs' ? epochActiveWallets.value : store.wallets
  return [...new Set(walletList.map(w => w?.function).filter(Boolean))].sort()
})

const currentEpochRows = computed(() => {
  const g = currentEpochGroup.value
  if (!g) return []
  const picked = selectedEpochWallets.value
  return g.wallets
    .map(r => {
      const w = walletMap.value.get(r.wallet_id)
      return { ...r, wallet: w }
    })
    .filter(r => r.wallet && r.wallet.deleted_at == null && (r.in_qubic > 0 || r.out_qubic > 0))
    .filter(r => !picked.length || picked.includes(r.wallet_id))
    .filter(r => !selectedFunction.value || r.wallet?.function === selectedFunction.value)
    .sort((a, b) =>
      (a.wallet?.label || a.wallet?.id || '').toLowerCase()
        .localeCompare((b.wallet?.label || b.wallet?.id || '').toLowerCase())
    )
})

// Totals derived from the visible rows so header reflects wallet-filter selection
const currentEpochFilteredTotals = computed(() => {
  const rows = currentEpochRows.value
  const acc = {
    in_qubic: 0, in_qubic_tx: 0, in_qubic_event: 0,
    in_tx_count: 0, in_event_count: 0,
    out_qubic: 0, out_qubic_tx: 0, out_qubic_event: 0,
    out_tx_count: 0, out_event_count: 0,
    in_eur: 0, in_usd: 0,
    out_eur: 0, out_usd: 0,
    wallet_count: rows.length,
  }
  for (const r of rows) {
    acc.in_qubic += r.in_qubic
    acc.in_qubic_tx += r.in_qubic_tx
    acc.in_qubic_event += r.in_qubic_event
    acc.in_tx_count += r.in_tx_count
    acc.in_event_count += r.in_event_count
    acc.out_qubic += r.out_qubic
    acc.out_qubic_tx += r.out_qubic_tx
    acc.out_qubic_event += r.out_qubic_event
    acc.out_tx_count += r.out_tx_count
    acc.out_event_count += r.out_event_count
    acc.in_eur += r.in_eur
    acc.in_usd += r.in_usd
    acc.out_eur += r.out_eur
    acc.out_usd += r.out_usd
  }
  return acc
})
</script>

<template>
  <div class="space-y-3">

    <PageHeader :title="t('nav.stats')"
                :hint="activeTab === 'epochs' ? t('stats.title_epochs') : t('stats.title_overview')">
      <button v-if="activeTab === 'epochs'"
              :class="['filter-pill inline-flex items-center gap-1.5', extended && 'filter-pill-active']"
              :title="t('stats.tt_extended')"
              @click="toggleExtended">
        <svg xmlns="http://www.w3.org/2000/svg"
             :class="['w-3.5 h-3.5 transition-transform', extended && 'rotate-180']"
             fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.4">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
        {{ t('stats.filter_extended') }}
      </button>
      <div v-if="activeTab === 'epochs' && availableEpochs.length" class="flex items-center gap-2">
        <label class="page-label">{{ t('stats.epoch_number') }}</label>
        <select :value="activeEpoch"
                class="input font-mono text-sm py-1 pl-2 pr-8 cursor-pointer hover:border-qubic-teal/60 transition-colors"
                @change="setSelectedEpoch(Number($event.target.value))">
          <option v-for="ep in availableEpochs" :key="ep" :value="ep">
            {{ ep }}{{ ep === availableEpochs[0] ? ' · ' + t('stats.current') : '' }}
          </option>
        </select>
      </div>
      <div class="tab-group">
        <button :class="['tab-btn', activeTab === 'epochs' && 'tab-btn-active']"
                @click="setActiveTab('epochs')">{{ t('stats.tab_epochs') }}</button>
        <button :class="['tab-btn', activeTab === 'overview' && 'tab-btn-active']"
                @click="setActiveTab('overview')">{{ t('stats.tab_overview') }}</button>
      </div>
    </PageHeader>

    <PageLoader v-if="loading" />
    <template v-else>

    <!-- =================== EPOCHEN TAB =================== -->
    <div v-if="activeTab === 'epochs'" class="space-y-3">
      <div v-if="!currentEpochGroup" class="card p-6 text-center text-gray-500 text-xs">
        {{ t('stats.no_epochs') }}
      </div>

      <template v-else>
        <!-- Wallet filter: only wallets with in/out activity in selected epoch -->
        <WalletFilter v-if="epochActiveWallets.length"
                      v-model="selectedEpochWallets"
                      :wallets="epochActiveWallets" />

        <!-- Funktions-Filter -->
        <div v-if="availableFunctions.length"
             class="card !py-2 !px-3 flex items-center flex-wrap gap-2">
          <div class="flex items-center gap-1.5 shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-qubic-teal/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
            </svg>
            <span class="text-xs text-gray-400 uppercase tracking-wide">{{ t('filter.function_filter') }}</span>
          </div>
          <button v-for="(fn, i) in availableFunctions" :key="fn"
                  :class="functionBtnClass(fn, i)"
                  @click="toggleFunction(fn)">
            {{ fn }}
          </button>
          <button v-if="selectedFunction"
                  class="btn-ghost text-xs py-0.5 px-2 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors ml-1"
                  @click="selectedFunction = null">
            {{ t('filter.clear_all') }}
          </button>
        </div>

        <!-- Header: epoch + aggregated totals (6 cols, icon + colored label per cell) -->
        <div class="card p-4 bg-gradient-to-r from-qubic-teal/5 to-qubic-teal/[0.02] border-qubic-teal/20">
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 divide-y sm:divide-y-0 sm:divide-x divide-qubic-border/50">
            <!-- 1: Epoche -->
            <div class="sm:pl-0 pb-3 sm:pb-0 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" :d="periodIcons.epoch"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-violet-400">{{ t('stats.epoch_number') }}</span>
              </div>
              <div class="font-mono text-base sm:text-xl text-violet-400 whitespace-nowrap">{{ currentEpochGroup.epoch }}</div>
            </div>

            <!-- 2: Incoming QUBIC -->
            <div class="sm:pl-4 pb-3 sm:pb-0 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-green-400">{{ t('stats.incoming_qubic') }}</span>
              </div>
              <div class="font-mono text-base sm:text-xl text-green-400 whitespace-nowrap">▲ {{ fmt(currentEpochFilteredTotals.in_qubic) }}</div>
            </div>

            <!-- 3: Incoming breakdown TX / EV -->
            <div class="sm:pl-4 pb-3 sm:pb-0 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055zM20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-gray-400">{{ t('stats.label_breakdown_in') }}</span>
              </div>
              <div class="text-xs font-mono leading-tight">
                <div class="text-amber-400/90 whitespace-nowrap">TX {{ fmt(currentEpochFilteredTotals.in_qubic_tx) }}</div>
                <div class="text-violet-400/90 whitespace-nowrap">EV {{ fmt(currentEpochFilteredTotals.in_qubic_event) }}</div>
              </div>
            </div>

            <!-- 4: Outgoing QUBIC -->
            <div class="sm:pl-4 pb-3 sm:pb-0 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-red-400">{{ t('stats.outgoing_qubic') }}</span>
              </div>
              <div class="font-mono text-base sm:text-xl text-red-400 whitespace-nowrap">▼ {{ fmt(currentEpochFilteredTotals.out_qubic) }}</div>
            </div>

            <!-- 5: Outgoing breakdown TX / EV -->
            <div class="sm:pl-4 pb-3 sm:pb-0 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055zM20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-gray-400">{{ t('stats.label_breakdown_out') }}</span>
              </div>
              <div class="text-xs font-mono leading-tight">
                <div class="text-amber-400/90 whitespace-nowrap">TX {{ fmt(currentEpochFilteredTotals.out_qubic_tx) }}</div>
                <div class="text-violet-400/90 whitespace-nowrap">EV {{ fmt(currentEpochFilteredTotals.out_qubic_event) }}</div>
              </div>
            </div>

            <!-- 6: Incoming EUR/USD -->
            <div class="sm:pl-4 min-w-0">
              <div class="flex items-center gap-1 mb-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
                </svg>
                <span class="text-xs uppercase tracking-wide text-emerald-400">{{ t('stats.incoming') }} {{ store.currency }}</span>
              </div>
              <div class="font-mono text-base sm:text-xl text-emerald-400 whitespace-nowrap" :title="fmtCurrencyAlt(currentEpochFilteredTotals[altInFiatKey])">{{ fmtCurrency(currentEpochFilteredTotals[inFiatKey]) }}</div>
            </div>
          </div>
        </div>

        <!-- Wallet panel grid -->
        <div v-if="currentEpochRows.length"
             class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <router-link v-for="r in currentEpochRows" :key="r.wallet_id" :to="`/wallets/${r.wallet_id}`"
                       class="card !p-3 text-left transition-all hover:border-qubic-teal/50 hover:shadow-lg hover:shadow-qubic-teal/10 group cq-panel">
            <!-- Header: wallet label + owner -->
            <div class="flex items-start justify-between gap-2 mb-1">
              <div class="flex items-center gap-1.5 min-w-0 flex-1">
                <OwnerIcon :type="r.wallet.wallet_type" size="w-4 h-4" />
                <span class="font-medium text-sm truncate group-hover:text-qubic-teal transition-colors">
                  {{ maskLabel(r.wallet.label, r.wallet.id) }}
                </span>
              </div>
              <div class="flex items-center gap-1 text-xs text-gray-400 min-w-0 max-w-[45%]">
                <OwnerIcon :type="r.wallet.wallet_type" size="w-3 h-3 shrink-0" />
                <span class="truncate" :title="store.hideAddresses ? '' : (r.wallet.owner || '')">{{ store.hideAddresses ? '••••••' : (r.wallet.owner || '—') }}</span>
              </div>
            </div>

            <!-- Function (left) + type pill (right), wraps on narrow widths -->
            <div class="flex items-center justify-between gap-2 flex-wrap mb-2">
              <span v-if="r.wallet.function" class="text-xs text-gray-500 truncate min-w-0">
                {{ r.wallet.function }}
              </span>
              <span v-else></span>
              <span :class="['pill text-xs py-0.5 px-2 shrink-0', r.wallet.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
                {{ r.wallet.wallet_type }}
              </span>
            </div>

            <!-- Two-column grid: Incoming (left) vs Outgoing (right).
                 With "Alles anzeigen" OFF (default), only rows with data render,
                 so panels stay compact. Empty columns collapse to 1 column. -->
            <div :class="[(extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'grid grid-cols-2 gap-3' : 'grid grid-cols-1 gap-2']">
              <!-- Incoming column (hidden only when outgoing-only and not extended) -->
              <div v-if="extended || r.in_qubic > 0" class="space-y-0.5 cq-panel min-w-0 overflow-hidden">
                <InfoLabel :label="`${t('stats.label_incoming')} QUBIC`" :tooltip="t('stats.tt_incoming')" />
                <div class="font-mono value-fit-lg whitespace-nowrap"
                     :class="r.in_qubic > 0 ? 'text-green-400' : 'text-gray-600'">
                  <template v-if="r.in_qubic > 0">▲ {{ fmt(r.in_qubic) }}</template>
                  <template v-else>—</template>
                </div>
                <template v-if="extended || r.in_qubic > 0">
                  <InfoLabel :label="`${t('stats.label_fiat')} ${store.currency}`" :tooltip="t('stats.tt_fiat')" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.in_qubic > 0 ? 'text-gray-400' : 'text-gray-600'"
                       :title="r.in_qubic > 0 ? fmtCurrencyAlt(r[altInFiatKey]) : undefined">
                    <template v-if="r.in_qubic > 0">{{ fmtCurrency(r[inFiatKey]) }}</template>
                    <template v-else>—</template>
                  </div>
                </template>
                <template v-if="extended || r.in_qubic_tx > 0">
                  <InfoLabel :label="t('stats.label_via_tx')" :tooltip="t('stats.tt_via_tx')" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.in_qubic_tx > 0 ? 'text-amber-400' : 'text-gray-600'">
                    <template v-if="r.in_qubic_tx > 0">
                      {{ fmt(r.in_qubic_tx) }}
                      <span class="text-amber-400/60">({{ r.in_tx_count }})</span>
                    </template>
                    <template v-else>—</template>
                  </div>
                </template>
                <template v-if="extended || r.in_qubic_event > 0">
                  <InfoLabel :label="t('stats.label_via_events')" :tooltip="t('stats.tt_via_events')" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.in_qubic_event > 0 ? 'text-violet-400' : 'text-gray-600'">
                    <template v-if="r.in_qubic_event > 0">
                      {{ fmt(r.in_qubic_event) }}
                      <span class="text-violet-400/60">({{ r.in_event_count }})</span>
                    </template>
                    <template v-else>—</template>
                  </div>
                </template>
              </div>

              <!-- Outgoing column (hidden when no outgoing data and not extended) -->
              <div v-if="extended || r.out_qubic > 0"
                   :class="['space-y-0.5 cq-panel min-w-0 overflow-hidden',
                            (extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'text-right' : '']">
                <InfoLabel :label="`${t('stats.label_outgoing')} QUBIC`" :tooltip="t('stats.tt_outgoing')"
                           :class="(extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'justify-end' : ''" />
                <div class="font-mono value-fit-lg whitespace-nowrap"
                     :class="r.out_qubic > 0 ? 'text-red-400' : 'text-gray-600'">
                  <template v-if="r.out_qubic > 0">▼ {{ fmt(r.out_qubic) }}</template>
                  <template v-else>—</template>
                </div>
                <template v-if="extended || r.out_qubic > 0">
                  <InfoLabel :label="`${t('stats.label_fiat')} ${store.currency}`" :tooltip="t('stats.tt_fiat')"
                             :class="(extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'justify-end' : ''" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.out_qubic > 0 ? 'text-gray-400' : 'text-gray-600'"
                       :title="r.out_qubic > 0 ? fmtCurrencyAlt(r[altOutFiatKey]) : undefined">
                    <template v-if="r.out_qubic > 0">{{ fmtCurrency(r[outFiatKey]) }}</template>
                    <template v-else>—</template>
                  </div>
                </template>
                <template v-if="extended || r.out_qubic_tx > 0">
                  <InfoLabel :label="t('stats.label_via_tx')" :tooltip="t('stats.tt_via_tx')"
                             :class="(extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'justify-end' : ''" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.out_qubic_tx > 0 ? 'text-amber-400' : 'text-gray-600'">
                    <template v-if="r.out_qubic_tx > 0">
                      {{ fmt(r.out_qubic_tx) }}
                      <span class="text-amber-400/60">({{ r.out_tx_count }})</span>
                    </template>
                    <template v-else>—</template>
                  </div>
                </template>
                <template v-if="extended || r.out_qubic_event > 0">
                  <InfoLabel :label="t('stats.label_via_events')" :tooltip="t('stats.tt_via_events')"
                             :class="(extended || (r.in_qubic > 0 && r.out_qubic > 0)) ? 'justify-end' : ''" />
                  <div class="font-mono text-xs whitespace-nowrap"
                       :class="r.out_qubic_event > 0 ? 'text-violet-400' : 'text-gray-600'">
                    <template v-if="r.out_qubic_event > 0">
                      {{ fmt(r.out_qubic_event) }}
                      <span class="text-violet-400/60">({{ r.out_event_count }})</span>
                    </template>
                    <template v-else>—</template>
                  </div>
                </template>
              </div>
            </div>
          </router-link>
        </div>
        <div v-else class="card p-6 text-center text-gray-500 text-xs">
          {{ t('stats.no_events') }}
        </div>
      </template>
    </div>

    <!-- =================== ÜBERSICHT TAB =================== -->
    <div v-else class="space-y-3">

    <WalletFilter v-model="selectedWallets" />

    <!-- Funktions-Filter -->
    <div v-if="availableFunctions.length"
         class="card !py-2 !px-3 flex items-center flex-wrap gap-2">
      <div class="flex items-center gap-1.5 shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-qubic-teal/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
        </svg>
        <span class="text-xs text-gray-400 uppercase tracking-wide">{{ t('filter.function_filter') }}</span>
      </div>
      <button v-for="(fn, i) in availableFunctions" :key="fn"
              :class="functionBtnClass(fn, i)"
              @click="toggleFunction(fn)">
        {{ fn }}
      </button>
      <button v-if="selectedFunction"
              class="btn-ghost text-xs py-0.5 px-2 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors ml-1"
              @click="selectedFunction = null">
        {{ t('filter.clear_all') }}
      </button>
    </div>

    <!-- Gesamt-KPIs (icon + colored label + bold value, like Dashboard panels) -->
    <div v-if="totals" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="card !p-3">
        <div class="flex items-center gap-1 mb-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
          <span class="text-xs uppercase tracking-wide text-violet-400">{{ t('stats.events_total') }}</span>
        </div>
        <div class="text-base sm:text-xl font-bold text-violet-400 whitespace-nowrap">{{ fmt(totals.events) }}</div>
      </div>
      <div class="card !p-3">
        <div class="flex items-center gap-1 mb-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
          </svg>
          <span class="text-xs uppercase tracking-wide text-amber-400">{{ t('stats.tx_total') }}</span>
        </div>
        <div class="text-base sm:text-xl font-bold text-amber-400 whitespace-nowrap">{{ fmt(totals.tx) }}</div>
      </div>
      <div class="card !p-3">
        <div class="flex items-center gap-1 mb-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-qubic-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <span class="text-xs uppercase tracking-wide text-qubic-teal">{{ t('stats.volume_qubic') }}</span>
        </div>
        <div class="text-base sm:text-xl font-bold text-qubic-teal whitespace-nowrap">{{ fmt(totals.qubic) }}</div>
      </div>
      <div class="card !p-3">
        <div class="flex items-center gap-1 mb-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
          </svg>
          <span class="text-xs uppercase tracking-wide text-green-400">{{ t('stats.volume') }} {{ store.currency }}</span>
        </div>
        <div class="text-base sm:text-xl font-bold text-green-400 whitespace-nowrap">{{ fmtCurrency(totals.eur) }}</div>
      </div>
    </div>

    <!-- Perioden: aktuell vs. vorher -->
    <div v-if="stats" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <div v-for="p in periods" :key="p.key" class="card !p-3">
        <div class="flex items-center justify-between mb-1">
          <div class="flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" :class="['w-3 h-3 flex-shrink-0', periodColors[p.key]]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" :d="periodIcons[p.key]"/>
            </svg>
            <span :class="['text-sm uppercase tracking-wide', periodColors[p.key]]">{{ p.label }} QUBIC</span>
          </div>
          <span v-if="p.trend" :class="p.trend.up ? 'text-green-400' : 'text-red-400'" class="text-xs font-medium">
            {{ p.trend.up ? '↑' : '↓' }} {{ p.trend.pct }}%
          </span>
        </div>
        <div class="text-base sm:text-xl font-bold text-qubic-teal whitespace-nowrap">{{ fmt(p.cur.volume_qubic) }}</div>
        <div class="text-xs text-gray-400 mb-0.5 whitespace-nowrap" :title="fmtCurrencyAlt(p.cur[altVolumeKey])">{{ fmtCurrency(p.cur[volumeKey]) }}</div>
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-violet-400">{{ fmt(p.cur.event_count) }} Events</span>
          <span class="text-xs font-semibold text-amber-400">{{ fmt(p.cur.tx_count) }} TX</span>
        </div>
        <div class="mt-2 pt-2 border-t border-qubic-border">
          <div class="text-sm font-semibold text-gray-400 whitespace-nowrap">{{ fmt(p.prev.volume_qubic) }}</div>
          <div class="text-xs text-gray-400 mb-0.5 whitespace-nowrap" :title="fmtCurrencyAlt(p.prev[altVolumeKey])">{{ fmtCurrency(p.prev[volumeKey]) }}</div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-violet-400/70">{{ fmt(p.prev.event_count) }} Events</span>
            <span class="text-xs text-amber-400/70">{{ fmt(p.prev.tx_count) }} TX</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Charts -->
    <div v-if="hasData">
      <!-- Legende Live vs Snapshot -->
      <div class="flex items-center gap-4 text-sm text-gray-400 mb-3">
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-qubic-teal/60"></span> {{ t('stats.snapshot_label') }}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-qubic-teal/30"></span> {{ t('stats.live_label') }}
        </span>

        <!-- Toggle -->
        <div class="flex gap-2 ml-auto">
          <button v-for="[val, lbl] in [['count', t('stats.count')],['volume_qubic','Vol. QUBIC'],['volume_fiat',`Vol. ${store.currency}`]]"
                  :key="val"
                  :class="['btn-ghost text-sm py-1', mode === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                  @click="mode = val">
            {{ lbl }}
          </button>
        </div>
      </div>

      <!-- Linienchart: alle Wochen -->
      <div class="card mb-4" style="height:300px">
        <Line :data="lineData" :options="chartOptions" />
      </div>

      <!-- Balkendiagramm: letzte 12 Wochen TX vs Events -->
      <div class="card" style="height:260px">
        <div class="text-sm uppercase text-gray-400 mb-2">{{ t('stats.bar_chart_title') }}</div>
        <div style="height:210px">
          <Bar :data="barData" :options="chartOptions" />
        </div>
      </div>
    </div>

    <div v-else-if="stats" class="card text-center py-12 text-gray-500">
      {{ t('stats.no_events') }}
    </div>

    </div>

    </template>
  </div>
</template>
