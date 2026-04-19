<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import EventsTable from '../components/EventsTable.vue'

const props = defineProps({ id: String })
const store = useAppStore()

const events  = ref([])
const total   = ref(0)
const loading = ref(false)
const page    = ref(1)
const PAGE_SIZE = 50

const filterMode  = ref('all')   // 'all' | 'epoch' | 'month' | 'year'
const filterEpoch = ref('')
const filterMonth = ref('')
const filterYear  = ref('')

const wallet = computed(() => store.wallets.find(w => w.id === props.id))

const monthOptions = computed(() => {
  const opts = []
  const now = new Date()
  for (let i = 0; i < 24; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const lbl = d.toLocaleString('de-DE', { month: 'long', year: 'numeric' })
    opts.push({ val, lbl })
  }
  return opts
})

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return Array.from({ length: 6 }, (_, i) => y - i)
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function filterParams() {
  const p = { wallet_id: props.id }
  if (filterMode.value === 'epoch' && filterEpoch.value) p.epoch = Number(filterEpoch.value)
  if (filterMode.value === 'month' && filterMonth.value)  p.month = filterMonth.value
  if (filterMode.value === 'year'  && filterYear.value)   p.year  = Number(filterYear.value)
  return p
}

async function load() {
  loading.value = true
  try {
    const fp = filterParams()
    const [evts, cnt] = await Promise.all([
      api.events.list({ ...fp, limit: PAGE_SIZE, offset: (page.value - 1) * PAGE_SIZE }),
      api.events.count(fp),
    ])
    events.value = evts
    total.value  = cnt.count
  } finally {
    loading.value = false
  }
}

function setFilter(mode) {
  filterMode.value  = mode
  filterEpoch.value = ''
  filterMonth.value = ''
  filterYear.value  = ''
  page.value = 1
  load()
}

watch([filterEpoch, filterMonth, filterYear], () => { page.value = 1; load() })
watch(page, load)
onMounted(load)

function explorerUrl(addr) {
  return `https://explorer.qubic.org/network/address/${addr}`
}
</script>

<template>
  <div class="space-y-4">

    <!-- Wallet-Header -->
    <div v-if="wallet" class="card">
      <div class="flex items-start justify-between gap-3 flex-wrap">
        <div class="min-w-0">
          <div class="text-base font-bold">{{ wallet.label }}</div>
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            <span class="text-xs font-mono text-gray-400 break-all">
              {{ store.hideAddresses ? '••••••••••••••••••••' : wallet.id }}
            </span>
            <a :href="explorerUrl(wallet.id)" target="_blank" rel="noopener"
               class="text-gray-500 hover:text-qubic-teal flex-shrink-0" title="Im Qubic Explorer öffnen">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
          </div>
        </div>
        <span :class="['pill', wallet.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
          {{ wallet.wallet_type }}
        </span>
      </div>
    </div>

    <!-- Filter-Leiste -->
    <div class="flex flex-wrap gap-2 items-center">
      <button v-for="[mode, lbl] in [['all','Alle'],['epoch','Epoch'],['month','Monat'],['year','Jahr']]"
              :key="mode"
              :class="['btn-ghost text-xs py-1', filterMode === mode && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
              @click="setFilter(mode)">
        {{ lbl }}
      </button>

      <input v-if="filterMode === 'epoch'"
             v-model="filterEpoch" type="number" placeholder="Epoch-Nr…"
             class="input text-xs w-32 py-1" />

      <select v-if="filterMode === 'month'" v-model="filterMonth" class="input text-xs py-1">
        <option value="">Monat wählen…</option>
        <option v-for="m in monthOptions" :key="m.val" :value="m.val">{{ m.lbl }}</option>
      </select>

      <select v-if="filterMode === 'year'" v-model="filterYear" class="input text-xs py-1">
        <option value="">Jahr wählen…</option>
        <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
      </select>

      <span class="ml-auto text-xs text-gray-500">{{ total.toLocaleString('de-DE') }} Einträge</span>
    </div>

    <!-- Events-Tabelle -->
    <EventsTable :events="events" :loading="loading" />

    <!-- Paging -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-4 py-2">
      <button @click="page--" :disabled="page <= 1"
              class="btn-ghost text-xs py-1 disabled:opacity-40 disabled:cursor-not-allowed">
        ← Zurück
      </button>
      <span class="text-xs text-gray-400">Seite {{ page }} / {{ totalPages }}</span>
      <button @click="page++" :disabled="page >= totalPages"
              class="btn-ghost text-xs py-1 disabled:opacity-40 disabled:cursor-not-allowed">
        Weiter →
      </button>
    </div>

  </div>
</template>
