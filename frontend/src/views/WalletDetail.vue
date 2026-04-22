<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import EventsTable from '../components/EventsTable.vue'
import { useTranslation } from 'i18next-vue'

const props = defineProps({ id: String })
const store = useAppStore()
const { t } = useTranslation()

const events  = ref([])
const total   = ref(0)
const loading = ref(false)
const page    = ref(1)
const PAGE_SIZE = 50

const filterMode  = ref('all')   // 'all' | 'epoch' | 'month' | 'year'
const filterEpoch = ref('')
const filterMonth = ref('')
const filterYear  = ref('')

const availableYears  = ref([])
const availableMonths = ref([])
const availableEpochs = ref([])

const wallet = computed(() => store.wallets.find(w => w.id === props.id))

const monthOptions = computed(() =>
  availableMonths.value.map(val => {
    const [y, m] = val.split('-')
    const lbl = new Date(+y, +m - 1, 1).toLocaleString(store.lang === 'de' ? 'de-DE' : 'en-US', { month: 'long', year: 'numeric' })
    return { val, lbl }
  })
)

const yearOptions = computed(() => availableYears.value)

async function loadFilterOptions() {
  try {
    const opts = await api.events.filterOptions(props.id)
    availableYears.value  = opts.years
    availableMonths.value = opts.months
    availableEpochs.value = opts.epochs
  } catch (e) { console.error(e) }
}

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
onMounted(() => { load(); loadFilterOptions() })

function maskLabel(label, id) {
  if (!store.hideAddresses) return label
  const n = id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 101
  return `Wallet ${n}`
}

function explorerUrl(addr) {
  return `https://explorer.qubic.org/network/address/${addr}`
}

async function copyAddress(addr) {
  if (addr) await navigator.clipboard.writeText(addr)
}
</script>

<template>
  <div class="space-y-2">

    <!-- Wallet-Header -->
    <div v-if="wallet" class="card">
      <div class="flex items-start justify-between gap-3 flex-wrap">
        <div class="min-w-0">
          <div class="text-base font-bold">{{ maskLabel(wallet.label, wallet.id) }}</div>
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            <span class="text-xs font-mono text-gray-400 break-all">
              {{ store.hideAddresses ? '••••••••••••••••••••' : wallet.id }}
            </span>
            <button v-if="!store.hideAddresses" @click="copyAddress(wallet.id)"
                    class="text-gray-400 hover:text-qubic-teal flex-shrink-0 transition-colors" :title="t('assets.copy')">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <a :href="explorerUrl(wallet.id)" target="_blank" rel="noopener"
               class="text-gray-400 hover:text-qubic-teal flex-shrink-0 transition-colors" :title="t('walletDetail.explorer')">
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
      <button v-for="[mode, lbl] in [['all', t('filter.all')],['epoch', t('stats.epoch')],['month', t('stats.month')],['year', t('stats.year')]]"
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
        <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
      </select>

      <span class="ml-auto text-sm text-gray-500">{{ total.toLocaleString(store.lang === 'de' ? 'de-DE' : 'en-US') }} {{ t('walletDetail.entries') }}</span>
    </div>

    <!-- Events-Tabelle -->
    <EventsTable :events="events" :loading="loading" />

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
