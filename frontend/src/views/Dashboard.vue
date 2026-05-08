<script setup>
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'
import WalletFilter from '../components/WalletFilter.vue'
import PageHeader from '../components/PageHeader.vue'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()

const selectedWallets = ref([])
const loadingEvents   = ref(true)
const loadingStats    = ref(true)
const stats           = ref(null)

// Paging
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250, 500, 1000]
const pageSize   = ref(Number(localStorage.getItem('dashboardPageSize')) || 10)
const page       = ref(1)
const total      = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function onPageSizeChange() {
  localStorage.setItem('dashboardPageSize', pageSize.value)
  page.value = 1
  loadEvents()
}

// Filter
const filterMode  = ref('all')
const filterEpoch = ref('')
const filterMonth = ref('')
const filterYear  = ref('')

const availableYears  = ref([])
const availableMonths = ref([])
const availableEpochs = ref([])

// Search
const searchInput = ref('')
const searchQuery = ref('')
let searchTimer = null

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchQuery.value = searchInput.value.trim()
    page.value = 1
    loadEvents()
  }, 350)
}

// Local events (independent of store.events which is for WebSocket live-feed)
const events = ref([])

const monthOptions = computed(() =>
  availableMonths.value.map(val => {
    const [y, m] = val.split('-')
    const lbl = new Date(+y, +m - 1, 1).toLocaleString(store.locale, { month: 'long', year: 'numeric' })
    return { val, lbl }
  })
)

async function loadFilterOptions() {
  try {
    const opts = await api.events.filterOptions(null, selectedWallets.value)
    availableYears.value  = opts.years
    availableMonths.value = opts.months
    availableEpochs.value = opts.epochs
  } catch (e) { console.error(e) }
}

function filterParams() {
  const p = {}
  if (selectedWallets.value.length) p.wallet_ids = selectedWallets.value
  if (filterMode.value === 'epoch' && filterEpoch.value) p.epoch = Number(filterEpoch.value)
  if (filterMode.value === 'month' && filterMonth.value)  p.month = filterMonth.value
  if (filterMode.value === 'year'  && filterYear.value)   p.year  = Number(filterYear.value)
  if (searchQuery.value) p.search = searchQuery.value
  return p
}

async function loadStats() {
  loadingStats.value = true
  try { stats.value = await api.stats.current(selectedWallets.value) } catch (e) { console.error(e) }
  finally { loadingStats.value = false }
}

async function loadEvents() {
  loadingEvents.value = true
  try {
    const fp = filterParams()
    const [evts, cnt] = await Promise.all([
      api.events.list({ ...fp, limit: pageSize.value, offset: (page.value - 1) * pageSize.value }),
      api.events.count(fp),
    ])
    events.value = evts
    total.value  = cnt.count
  } catch (e) { console.error(e) }
  finally { loadingEvents.value = false }
}

function setFilter(mode) {
  filterMode.value  = mode
  filterEpoch.value = mode === 'epoch' ? (availableEpochs.value[0] ?? '') : ''
  filterMonth.value = mode === 'month' ? (availableMonths.value[0] ?? '') : ''
  filterYear.value  = mode === 'year'  ? (availableYears.value[0]  ?? '') : ''
  page.value = 1
  loadEvents()
}

watch(selectedWallets, () => {
  page.value = 1
  loadStats()
  loadFilterOptions()
  loadEvents()
}, { deep: true })

watch([filterEpoch, filterMonth, filterYear], () => { page.value = 1; loadEvents() })
watch(page, loadEvents)

onMounted(() => { loadStats(); loadFilterOptions(); loadEvents() })

const intervalId = setInterval(loadStats, 60_000)
onUnmounted(() => { clearInterval(intervalId); clearTimeout(searchTimer) })
</script>

<template>
  <div class="space-y-3">
    <PageHeader :title="t('nav.dashboard')" :hint="t('page_hint.dashboard')" />
    <WalletFilter v-model="selectedWallets" />
    <StatsPanel :stats="stats" :loading="loadingStats" />

    <!-- Filter-Leiste -->
    <div class="flex flex-wrap gap-2 items-center">
      <button
        v-for="[mode, lbl] in [['all', t('filter.all')],['epoch', t('stats.epoch')],['month', t('stats.month')],['year', t('stats.year')]]"
        :key="mode"
        :class="['btn-ghost text-sm py-1', filterMode === mode && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
        @click="setFilter(mode)">
        {{ lbl }}
      </button>

      <select v-if="filterMode === 'epoch'" v-model="filterEpoch" class="input text-sm py-1">
        <option value="">{{ t('walletDetail.select_epoch') }}</option>
        <option v-for="ep in availableEpochs" :key="ep" :value="ep">{{ ep }}</option>
      </select>

      <select v-if="filterMode === 'month'" v-model="filterMonth" class="input text-sm py-1">
        <option value="">{{ t('walletDetail.select_month') }}</option>
        <option v-for="m in monthOptions" :key="m.val" :value="m.val">{{ m.lbl }}</option>
      </select>

      <select v-if="filterMode === 'year'" v-model="filterYear" class="input text-sm py-1">
        <option value="">{{ t('walletDetail.select_year') }}</option>
        <option v-for="y in availableYears" :key="y" :value="y">{{ y }}</option>
      </select>

      <!-- Suchfeld -->
      <div class="relative ml-auto">
        <input
          v-model="searchInput"
          @input="onSearchInput"
          type="text"
          :placeholder="t('dashboard.search_placeholder')"
          class="input text-sm py-1 pl-8 w-52"
        />
        <svg class="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500 pointer-events-none"
             xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <button v-if="searchInput" @click="searchInput = ''; searchQuery = ''; page = 1; loadEvents()"
                class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-xs">✕</button>
      </div>

      <div class="flex items-center gap-2 whitespace-nowrap">
        <span class="text-sm text-gray-500">{{ total.toLocaleString(store.locale) }} {{ t('walletDetail.entries') }}</span>
        <select v-model="pageSize" @change="onPageSizeChange" class="input text-sm py-1 w-20">
          <option v-for="n in PAGE_SIZE_OPTIONS" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
    </div>

    <!-- Events-Tabelle -->
    <EventsTable :events="events" :loading="loadingEvents" :readonly="true" />

    <!-- Paging -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-4 py-2">
      <button @click="page--" :disabled="page <= 1"
              class="btn-ghost text-sm py-1 disabled:opacity-40 disabled:cursor-not-allowed">
        {{ t('walletDetail.prev') }}
      </button>
      <span class="text-xs text-gray-400">{{ t('walletDetail.page') }} {{ page }} / {{ totalPages }}</span>
      <button @click="page++" :disabled="page >= totalPages"
              class="btn-ghost text-sm py-1 disabled:opacity-40 disabled:cursor-not-allowed">
        {{ t('walletDetail.next') }}
      </button>
    </div>
  </div>
</template>
