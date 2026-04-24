<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import EventsTable from '../components/EventsTable.vue'
import PageHeader from '../components/PageHeader.vue'
import BackButton from '../components/BackButton.vue'
import { useTranslation } from 'i18next-vue'
import { useQubicUtils } from '../composables/useQubicUtils'

const props = defineProps({ id: String })
const store = useAppStore()
const { t } = useTranslation()
const { explorerUrl, copyAddress, maskLabel } = useQubicUtils()
const router = useRouter()

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/wallets')
}

const events  = ref([])
const total   = ref(0)
const loading = ref(false)
const page    = ref(1)

// Opening positions
const openingPositions = ref([])
const showAddPos   = ref(false)
const addError     = ref('')
const posError     = ref('')
const priceLoading = ref(false)
const newPos       = ref({ date: '', amount_qubic: '', price_eur: '', price_usd: '', note: '' })

watch(() => newPos.value.date, async (date) => {
  if (!date) return
  priceLoading.value = true
  try {
    const p = await api.tax.getPriceForDate(date)
    if (p.eur != null) newPos.value.price_eur = p.eur
    if (p.usd != null) newPos.value.price_usd = p.usd
  } catch (e) {
    console.error(e)
  } finally {
    priceLoading.value = false
  }
})

function fmtPrice(val) {
  if (val == null) return '—'
  return Number(val).toFixed(10).replace(/\.?0+$/, '') || '0'
}

async function loadOpeningPositions() {
  try { openingPositions.value = await api.tax.getOpeningPositions(props.id) || [] }
  catch (e) { console.error(e) }
}

async function addOpeningPosition() {
  addError.value = ''
  const p = newPos.value
  if (!p.date || !p.amount_qubic) { addError.value = t('tax.opening_required_fields'); return }
  try {
    const created = await api.tax.createOpeningPosition({
      wallet_id: props.id,
      date: p.date,
      amount_qubic: parseInt(p.amount_qubic, 10),
      price_eur: p.price_eur ? parseFloat(p.price_eur) : null,
      price_usd: p.price_usd ? parseFloat(p.price_usd) : null,
      note: p.note || null,
    })
    openingPositions.value.push(created)
    newPos.value = { date: '', amount_qubic: '', price_eur: '', price_usd: '', note: '' }
    showAddPos.value = false
  } catch (e) {
    addError.value = t('common.error_prefix') + e.message
  }
}

async function deleteOpeningPosition(id) {
  if (!confirm(t('tax.opening_delete_confirm'))) return
  posError.value = ''
  try {
    await api.tax.deleteOpeningPosition(id)
    openingPositions.value = openingPositions.value.filter(p => p.id !== id)
  } catch (e) {
    posError.value = t('tax.opening_delete_error')
  }
}
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
    const lbl = new Date(+y, +m - 1, 1).toLocaleString(store.locale, { month: 'long', year: 'numeric' })
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
onMounted(() => { load(); loadFilterOptions(); loadOpeningPositions() })


const resyncing = ref(false)
async function resyncTx() {
  resyncing.value = true
  try {
    await api.wallets.resyncTx(props.id)
  } finally {
    resyncing.value = false
  }
}
</script>

<template>
  <div class="space-y-3">

    <PageHeader :title="t('nav.wallets')" :hint="wallet ? maskLabel(wallet.label, wallet.id) : ''" />
    <div class="!mt-1">
      <BackButton :label="t('common.back')" @click="goBack" />
    </div>

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
                    class="icon-btn" :title="t('assets.copy')">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <a :href="explorerUrl(wallet.id)" target="_blank" rel="noopener"
               class="icon-btn" :title="t('walletDetail.explorer')">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
          </div>
        </div>
        <div class="flex flex-col items-end gap-1.5">
          <div class="flex items-center gap-2">
            <button :disabled="resyncing"
                    :title="resyncing ? 'Resyncing…' : 'Re-Sync TX'"
                    :class="['text-xs text-gray-500 hover:text-qubic-teal transition-colors disabled:opacity-40', resyncing && 'animate-spin']"
                    @click="resyncTx">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </button>
            <span :class="['pill', wallet.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
              {{ wallet.wallet_type }}
            </span>
            <span v-if="wallet.function" class="pill bg-sky-500/20 text-sky-400 border-sky-500/30">
              {{ wallet.function }}
            </span>
          </div>
          <div class="text-right">
            <div class="text-xs text-gray-400 uppercase tracking-wide">{{ t('wallet.balance') }} QU</div>
            <div class="flex items-center justify-end gap-1.5 mt-0.5">
              <span class="font-mono text-sm" :class="wallet.balance == null ? 'text-gray-600 italic' : 'text-gray-200'">
                {{ wallet.balance == null ? t('wallet.balance_pending') : (store.hideAddresses ? '••••••' : wallet.balance.toLocaleString(store.locale)) }}
              </span>
              <span v-if="wallet.balance != null"
                    :class="['text-xs', wallet.balance_live == null ? 'text-gray-500' : wallet.balance === wallet.balance_live ? 'text-green-400' : 'text-yellow-400']"
                    :title="wallet.balance_live == null ? t('wallet.balance_no_live') : wallet.balance === wallet.balance_live ? t('wallet.balance_synced') : t('wallet.balance_drift')">●</span>
            </div>
            <div v-if="wallet.balance != null && wallet.balance_live != null && wallet.balance !== wallet.balance_live"
                 class="text-xs text-yellow-400 mt-0.5">
              {{ t('wallet.balance_drift') }}: {{ store.hideAddresses ? '••••••' : wallet.balance_live.toLocaleString(store.locale) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Opening Positions -->
    <div class="card">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('tax.opening_positions') }}</h3>
        <button class="btn-ghost text-sm py-1.5 px-3" @click="showAddPos = !showAddPos; addError = ''">
          + {{ t('tax.opening_add') }}
        </button>
      </div>

      <!-- Add form -->
      <div v-if="showAddPos" class="rounded-lg border border-qubic-border bg-qubic-bg/50 p-4 mb-4 space-y-3">
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">{{ t('tax.opening_date') }}</label>
            <input v-model="newPos.date" type="date" class="input w-full text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">{{ t('tax.opening_amount') }}</label>
            <input v-model="newPos.amount_qubic" type="number" min="1" class="input w-full text-sm" placeholder="0" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">
              {{ t('tax.opening_price_eur') }}
              <span v-if="priceLoading" class="ml-1 text-qubic-teal">↻</span>
            </label>
            <input v-model="newPos.price_eur" type="number" step="0.00000001" class="input w-full text-sm" placeholder="0.00" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">
              {{ t('tax.opening_price_usd') }}
              <span v-if="priceLoading" class="ml-1 text-qubic-teal">↻</span>
            </label>
            <input v-model="newPos.price_usd" type="number" step="0.00000001" class="input w-full text-sm" placeholder="0.00" />
          </div>
          <div class="col-span-2 sm:col-span-2">
            <label class="text-xs text-gray-500 block mb-1">{{ t('tax.opening_note') }}</label>
            <input v-model="newPos.note" type="text" class="input w-full text-sm" placeholder="…" />
          </div>
        </div>
        <p v-if="addError" class="text-red-400 text-xs">{{ addError }}</p>
        <div class="flex gap-2 justify-end">
          <button class="btn-ghost text-sm py-1.5 px-4" @click="showAddPos = false; addError = ''">{{ t('common.cancel') }}</button>
          <button class="btn text-sm py-1.5 px-4" @click="addOpeningPosition">{{ t('common.save') }}</button>
        </div>
      </div>

      <p v-if="posError" class="text-red-400 text-xs mt-2">{{ posError }}</p>

      <!-- List -->
      <div v-if="openingPositions.length" class="overflow-x-auto">
        <table class="table-std">
          <thead>
            <tr class="border-b border-qubic-border text-gray-500 uppercase">
              <th class="text-left py-2 pr-3">{{ t('tax.opening_date') }}</th>
              <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.opening_amount') }}</th>
              <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.opening_price_eur') }}</th>
              <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.opening_price_usd') }}</th>
              <th class="text-left py-2 pr-3">{{ t('tax.opening_note') }}</th>
              <th class="py-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in openingPositions" :key="p.id"
                class="border-b border-qubic-border/30 hover:bg-qubic-teal/5 transition-colors">
              <td class="py-2 pr-3 whitespace-nowrap">{{ p.date }}</td>
              <td class="py-2 pr-3 text-right font-mono">{{ Number(p.amount_qubic).toLocaleString(store.locale) }}</td>
              <td class="py-2 pr-3 text-right font-mono">{{ fmtPrice(p.price_eur) }}</td>
              <td class="py-2 pr-3 text-right font-mono">{{ fmtPrice(p.price_usd) }}</td>
              <td class="py-2 pr-3 text-gray-400">{{ p.note || '' }}</td>
              <td class="py-2 text-right">
                <button class="text-red-400/60 hover:text-red-400 transition-colors" @click="deleteOpeningPosition(p.id)">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="text-xs text-gray-500">—</p>
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

      <span class="ml-auto text-sm text-gray-500">{{ total.toLocaleString(store.locale) }} {{ t('walletDetail.entries') }}</span>
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
