<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import { useAppStore } from '../stores/app'
import { Line, Bar } from 'vue-chartjs'
import WalletFilter from '../components/WalletFilter.vue'
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, Filler,
} from 'chart.js'

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, CategoryScale, LinearScale, PointElement, Filler)

const { t } = useTranslation()
const store = useAppStore()

const currencySymbol = computed(() => store.currency === 'USD' ? '$' : '€')
const volumeKey      = computed(() => store.currency === 'USD' ? 'volume_usd' : 'volume_eur')
const stats          = ref(null)
const snaps          = ref([])
const history        = ref([])
const mode           = ref('count')
const selectedWallets = ref([])

async function loadStats() {
  const ids = selectedWallets.value
  ;[stats.value, snaps.value, history.value] = await Promise.all([
    api.stats.current(ids),
    ids.length ? Promise.resolve([]) : api.stats.snapshots(),
    api.stats.history('week', ids),
  ])
}

watch(selectedWallets, loadStats, { deep: true })
onMounted(loadStats)

// ── Formatierung ────────────────────────────────────────────────
function fmt(n)    { return n == null ? '—' : Number(n).toLocaleString('de-DE') }
function fmtCurrency(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ' + currencySymbol.value
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
// Snapshots liefern historische Wochen (Mittwoch-Marker).
// History liefert alle Wochen direkt aus der events-Tabelle.
// Regel: Snapshot hat Vorrang (genauer); Live-Wochen ohne Snapshot werden ergänzt.
const mergedData = computed(() => {
  // Snapshots in Map: key = "YYYY-WW"
  const snapMap = new Map()
  for (const s of snaps.value) {
    const key = `${s.year}-${String(s.week).padStart(2, '0')}`
    snapMap.set(key, { ...s, source: 'snapshot' })
  }

  // History-Einträge die noch kein Snapshot haben → als "live" markieren
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

// ── Gesamt-KPIs ─────────────────────────────────────────────────
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

// ── Chart-Farben: snapshot = teal/amber, live = hellere Variante ─
function borderColor(item, baseColor) { return item.source === 'live' ? baseColor + '99' : baseColor }

// ── Liniendiagramm ───────────────────────────────────────────────
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
        { label: `Volumen ${store.currency}`, data: items.map(s => +((s[volumeKey.value]) || 0).toFixed(2)),
          borderColor: '#2dd4bf', backgroundColor: 'rgba(45,212,191,0.1)', fill: true, tension: 0.4 },
      ],
    }
  }
  return {
    labels,
    datasets: [
      { label: 'Volumen QUBIC', data: items.map(s => s.volume_qubic || 0),
        borderColor: '#2dd4bf', backgroundColor: 'rgba(45,212,191,0.1)', fill: true, tension: 0.4 },
    ],
  }
})

// ── Balkendiagramm letzte 12 Wochen ─────────────────────────────
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
</script>

<template>
  <div class="space-y-6">

    <WalletFilter v-model="selectedWallets" />

    <!-- Gesamt-KPIs -->
    <div v-if="totals" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="card text-center">
        <div class="text-xs uppercase text-gray-400 mb-1">Events gesamt</div>
        <div class="text-2xl font-bold text-qubic-teal">{{ fmt(totals.events) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-xs uppercase text-gray-400 mb-1">TX gesamt</div>
        <div class="text-2xl font-bold text-amber-400">{{ fmt(totals.tx) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-xs uppercase text-gray-400 mb-1">Volumen QUBIC</div>
        <div class="text-2xl font-bold">{{ fmt(totals.qubic) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-xs uppercase text-gray-400 mb-1">Volumen {{ store.currency }}</div>
        <div class="text-2xl font-bold text-green-400">{{ fmtCurrency(totals.eur) }}</div>
      </div>
    </div>

    <!-- Perioden: aktuell vs. vorher -->
    <div v-if="stats" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <div v-for="p in periods" :key="p.key" class="card">
        <div class="text-xs uppercase tracking-wide text-gray-400 mb-2 flex items-center justify-between">
          {{ p.label }}
          <span v-if="p.trend" :class="p.trend.up ? 'text-green-400' : 'text-red-400'" class="text-xs font-medium">
            {{ p.trend.up ? '↑' : '↓' }} {{ p.trend.pct }}%
          </span>
        </div>
        <div class="text-xl font-bold text-qubic-teal">{{ fmt(p.cur.volume_qubic) }} QU</div>
        <div class="text-xs text-gray-400">{{ fmt(p.cur.count) }} {{ t('stats.count') }}</div>
        <div class="text-[10px] text-gray-500 mt-0.5">{{ fmtCurrency(p.cur[volumeKey]) }}</div>
        <div class="mt-2 pt-2 border-t border-qubic-border">
          <div class="text-sm font-semibold text-gray-400">{{ fmt(p.prev.volume_qubic) }} QU</div>
          <div class="text-[10px] text-gray-500">{{ fmt(p.prev.count) }} {{ t('stats.count') }} · {{ fmtCurrency(p.prev[volumeKey]) }}</div>
        </div>
      </div>
    </div>

    <!-- Charts -->
    <div v-if="hasData">
      <!-- Legende Live vs Snapshot -->
      <div class="flex items-center gap-4 text-xs text-gray-400 mb-3">
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-qubic-teal/60"></span> Snapshot (Mi 12:00 UTC)
        </span>
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-3 h-3 rounded-sm bg-qubic-teal/30"></span> Live-Daten (noch kein Snapshot)
        </span>

        <!-- Toggle -->
        <div class="flex gap-2 ml-auto">
          <button v-for="[val, lbl] in [['count','Anzahl'],['volume_qubic','Vol. QU'],['volume_fiat',`Vol. ${store.currency}`]]"
                  :key="val"
                  :class="['btn-ghost text-xs py-1', mode === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
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
        <div class="text-xs uppercase text-gray-400 mb-2">TX vs. Events — letzte 12 Wochen</div>
        <div style="height:210px">
          <Bar :data="barData" :options="chartOptions" />
        </div>
      </div>
    </div>

    <div v-else-if="stats" class="card text-center py-12 text-gray-500">
      Noch keine Events in der Datenbank vorhanden.
    </div>

  </div>
</template>
