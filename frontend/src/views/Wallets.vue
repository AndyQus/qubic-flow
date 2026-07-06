<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'
import PageHeader from '../components/PageHeader.vue'
import OwnerIcon from '../components/OwnerIcon.vue'
import BackButton from '../components/BackButton.vue'
import { useQubicUtils } from '../composables/useQubicUtils'

function groupIconType(group) {
  return group.types.size === 1 ? [...group.types][0] : ''
}
function ownerIconType(ownerName) {
  const types = new Set(store.wallets.filter(w => w.owner === ownerName).map(w => w.wallet_type))
  return types.size === 1 ? [...types][0] : ''
}

const store = useAppStore()
const { t } = useTranslation()
const { explorerUrl, copyAddress, copyValue, fmtDecimal, fmtRateLocale, maskLabel } = useQubicUtils()
const router = useRouter()
const route = useRoute()

function goToWallet(id) { router.push(`/wallets/${id}`) }
const showForm        = ref(false)
const loading         = ref(true)
const editingId       = ref(null)
const error           = ref('')
const editError       = ref('')
const selectedOwner   = ref(null)
const configSortKey   = ref('label')
const configSortDir   = ref('asc')
const form            = ref({ id: '', label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })
const editForm        = ref({ label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })

function toggleConfigSort(key) {
  if (configSortKey.value === key) {
    configSortDir.value = configSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    configSortKey.value = key
    configSortDir.value = 'asc'
  }
}

const uniqueOwners = computed(() =>
  [...new Set(store.wallets.map(w => w.owner).filter(Boolean))].sort()
)

const uniqueFunctions = computed(() =>
  [...new Set(store.wallets.map(w => w.function).filter(Boolean))].sort()
)

const displayedWallets = computed(() => {
  const base = Array.isArray(store.filteredWallets) ? store.filteredWallets : []
  const filtered = !selectedOwner.value ? base : base.filter(w => w && w.owner === selectedOwner.value)
  return [...filtered].sort((a, b) => {
    let av, bv
    switch (configSortKey.value) {
      case 'label':    av = (a.label || a.id || '').toLowerCase();   bv = (b.label || b.id || '').toLowerCase();   break
      case 'owner':    av = (a.owner || '').toLowerCase();            bv = (b.owner || '').toLowerCase();            break
      case 'address':  av = (a.id || '').toLowerCase();               bv = (b.id || '').toLowerCase();               break
      case 'type':     av = (a.wallet_type || '').toLowerCase();      bv = (b.wallet_type || '').toLowerCase();      break
      case 'function': av = (a.function || '').toLowerCase();         bv = (b.function || '').toLowerCase();         break
      case 'note':     av = (a.note || '').toLowerCase();             bv = (b.note || '').toLowerCase();             break
      case 'balance':  av = a.balance ?? -Infinity;                   bv = b.balance ?? -Infinity;                   break
      case 'entries':  av = a.total_events ?? -1;                     bv = b.total_events ?? -1;                     break
      default:         av = ''; bv = ''
    }
    if (av < bv) return configSortDir.value === 'asc' ? -1 : 1
    if (av > bv) return configSortDir.value === 'asc' ? 1 : -1
    return 0
  })
})

async function reload() {
  loading.value = true
  try { store.wallets = await api.wallets.list() }
  finally { loading.value = false }
}

async function submit() {
  error.value = ''
  try {
    await api.wallets.create(form.value)
    form.value = { id: '', label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' }
    showForm.value = false
    await reload()
  } catch (e) {
    error.value = e.message.includes('409') ? t('wallet.address_exists') : `${t('node.url_error')}${e.message}`
  }
}

function startEdit(w) {
  editingId.value = w.id
  editForm.value = { label: w.label, owner: w.owner || '', function: w.function || '', note: w.note || '', wallet_type: w.wallet_type }
}

async function saveEdit(id) {
  editError.value = ''
  try {
    await api.wallets.update(id, editForm.value)
    editingId.value = null
    await reload()
  } catch (e) {
    editError.value = e.message
  }
}

function cancelEdit() { editingId.value = null }

async function remove(id) {
  if (!confirm(t('wallet.delete_confirm'))) return
  try {
    await api.wallets.remove(id)
    await reload()
  } catch (e) {
    error.value = e.message
  }
}


function fmtBalance(w) {
  if (w.balance == null) return t('wallet.balance_pending')
  if (store.hideAddresses) return '••••••'
  return w.balance.toLocaleString(store.locale)
}

function balanceSyncClass(w) {
  if (w.balance == null || w.balance_live == null) return 'text-gray-500'
  return w.balance === w.balance_live ? 'text-green-400' : 'text-yellow-400'
}

function balanceSyncTitle(w) {
  if (w.balance == null) return ''
  if (w.balance_live == null) return t('wallet.balance_no_live')
  return w.balance === w.balance_live ? t('wallet.balance_synced') : `${t('wallet.balance_drift')}: ${w.balance_live.toLocaleString(store.locale)}`
}

// Tabs & Portfolio selection — synced to URL query (?tab=, ?owner=, ?view=)
const activeTab = ref(route.query.tab === 'config' ? 'config' : 'portfolio')
const selectedPortfolioOwner = ref(route.query.owner || null)
const portfolioView = ref(route.query.view === 'assets' ? 'assets' : 'qubic')

watch(() => route.query, (q) => {
  activeTab.value = q.tab === 'config' ? 'config' : 'portfolio'
  selectedPortfolioOwner.value = q.owner || null
  portfolioView.value = q.view === 'assets' ? 'assets' : 'qubic'
})

function setActiveTab(tab) {
  const q = {}
  if (tab === 'config') q.tab = 'config'
  router.push({ path: '/wallets', query: q })
}

function setPortfolioView(view) {
  const q = { ...route.query }
  if (view === 'assets') q.view = 'assets'
  else delete q.view
  router.push({ path: '/wallets', query: q })
}

function selectPortfolioOwner(owner) {
  router.push({ path: '/wallets', query: { ...route.query, owner } })
}

function backToOwners() {
  const q = { ...route.query }
  delete q.owner
  router.push({ path: '/wallets', query: q })
}

// Portfolio data: current price + opening positions for unrealized P&L
const currentPrice = ref(null)      // { eur, usd } | null
const openingPositions = ref([])     // [{wallet_id, amount_qubic, price_eur, price_usd, ...}]

async function loadPortfolioData() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  const dateStr = d.toISOString().slice(0, 10)
  const [price, positions] = await Promise.all([
    api.tax.getPriceForDate(dateStr).catch(() => null),
    api.tax.getOpeningPositions().catch(() => []),
  ])
  currentPrice.value = price
  openingPositions.value = Array.isArray(positions) ? positions : []
}

const unitPrice = computed(() => {
  if (!currentPrice.value) return null
  return store.currency === 'USD' ? currentPrice.value.usd : currentPrice.value.eur
})

const costBasisMap = computed(() => {
  const map = new Map()
  const priceField = store.currency === 'USD' ? 'price_usd' : 'price_eur'
  for (const p of openingPositions.value) {
    const px = p[priceField]
    if (px == null || px === 0) continue
    const cb = (p.amount_qubic ?? 0) * px
    map.set(p.wallet_id, (map.get(p.wallet_id) ?? 0) + cb)
  }
  return map
})

function walletValue(w) {
  if (w.balance == null || unitPrice.value == null) return null
  return w.balance * unitPrice.value
}

function walletCost(w) {
  return costBasisMap.value.get(w.id) ?? null
}

function walletPnl(w) {
  const v = walletValue(w)
  const c = walletCost(w)
  if (v == null || c == null || c === 0) return null
  return v - c
}

function walletPnlPct(w) {
  const v = walletValue(w)
  const c = walletCost(w)
  if (v == null || c == null || c === 0) return null
  return ((v - c) / c) * 100
}

const fiatSymbol = computed(() => store.currency === 'USD' ? '$' : '€')
const altFiatSymbol = computed(() => store.currency === 'USD' ? '€' : '$')
const unitPriceAlt = computed(() => {
  if (!currentPrice.value) return null
  return store.currency === 'USD' ? currentPrice.value.eur : currentPrice.value.usd
})

function fmtFiat(n) {
  if (n == null) return '—'
  if (store.hideAddresses) return '••••••'
  return `${n.toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${fiatSymbol.value}`
}

function fmtFiatAlt(n) {
  if (n == null || unitPrice.value == null || !unitPriceAlt.value || store.hideAddresses) return undefined
  const alt = n * (unitPriceAlt.value / unitPrice.value)
  return `${alt.toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${altFiatSymbol.value}`
}

function fmtPct(n) {
  if (n == null) return ''
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

const ownerGroups = computed(() => {
  const wallets = Array.isArray(store.filteredWallets) ? store.filteredWallets : []
  const map = new Map()
  const px = unitPrice.value
  const cbMap = costBasisMap.value
  for (const w of wallets) {
    const key = w.owner || '—'
    if (!map.has(key)) map.set(key, {
      owner: key, wallets: [], totalBalance: 0, hasNullBalance: false,
      totalEvents: 0, types: new Set(),
      totalValue: 0, totalCost: 0, hasValue: false, hasCost: false,
    })
    const g = map.get(key)
    g.wallets.push(w)
    if (w.balance != null) {
      g.totalBalance += w.balance
      if (px != null) { g.totalValue += w.balance * px; g.hasValue = true }
    } else g.hasNullBalance = true
    if (w.total_events != null) g.totalEvents += w.total_events
    g.types.add(w.wallet_type)
    const cb = cbMap.get(w.id)
    if (cb != null && cb > 0) { g.totalCost += cb; g.hasCost = true }
  }
  const groups = [...map.values()]
  for (const g of groups) {
    g.wallets.sort((a, b) =>
      (a.label || a.id || '').toLowerCase().localeCompare((b.label || b.id || '').toLowerCase())
    )
  }
  return groups.sort((a, b) => {
    if (a.owner === '—') return 1
    if (b.owner === '—') return -1
    const aKey = (a.wallets[0]?.label || a.wallets[0]?.id || a.owner || '').toLowerCase()
    const bKey = (b.wallets[0]?.label || b.wallets[0]?.id || b.owner || '').toLowerCase()
    return aKey.localeCompare(bKey)
  })
})

const selectedGroup = computed(() =>
  ownerGroups.value.find(g => g.owner === selectedPortfolioOwner.value) || null
)

const grandTotal = computed(() => {
  let balance = 0, value = 0, cost = 0, hasValue = false, hasCost = false
  for (const g of ownerGroups.value) {
    balance += g.totalBalance
    if (g.hasValue) { value += g.totalValue; hasValue = true }
    if (g.hasCost)  { cost  += g.totalCost;  hasCost  = true }
  }
  return { balance, value, cost, hasValue, hasCost }
})

// ── Token/Shares view (assets summary for all wallets) ─────────
const assetsSummary = ref(null)   // { wallets: {id: {assets, total_value_*}}, qu_rate }
const assetsLoading = ref(false)

async function loadAssetsSummary() {
  if (assetsSummary.value || assetsLoading.value) return
  assetsLoading.value = true
  try {
    assetsSummary.value = await api.wallets.assetsSummary()
  } catch (e) {
    console.error(e)
    assetsSummary.value = { wallets: {}, qu_rate: null }
  } finally {
    assetsLoading.value = false
  }
}

watch(portfolioView, (v) => { if (v === 'assets') loadAssetsSummary() }, { immediate: true })

const walletAssetsMap = computed(() => assetsSummary.value?.wallets || {})
const assetFiatField = computed(() => store.currency === 'USD' ? 'total_value_usd' : 'total_value_eur')
const assetValueField = computed(() => store.currency === 'USD' ? 'value_usd' : 'value_eur')

function walletAssets(w) {
  const assets = walletAssetsMap.value[w.id]?.assets || []
  return [...assets].sort((a, b) => (a.name || '').localeCompare(b.name || ''))
}

function walletAssetsFiat(w) {
  const entry = walletAssetsMap.value[w.id]
  if (!entry || !entry.assets.length) return null
  return entry[assetFiatField.value]
}

// Total wallet value = QUBIC value + token/share value.
// Only combine once BOTH are known — the QUBIC rate loads separately
// (loadPortfolioData) and can lag behind the token summary, which would
// otherwise make the total look smaller than the token value alone.
function walletTotalFiat(w) {
  const qu = walletValue(w)
  const tok = walletAssetsFiat(w)
  if (qu == null) return null
  return qu + (tok ?? 0)
}

// Owner groups enriched with token totals for the assets view
const ownerAssetGroups = computed(() => {
  return ownerGroups.value.map(g => {
    let tokenValue = 0
    let hasTokens = false
    const tokenCounts = new Map()   // name -> { units, kind }
    for (const w of g.wallets) {
      const entry = walletAssetsMap.value[w.id]
      if (!entry || !entry.assets.length) continue
      hasTokens = true
      for (const a of entry.assets) {
        const existing = tokenCounts.get(a.name)
        tokenCounts.set(a.name, { units: (existing?.units || 0) + a.units, kind: a.kind })
      }
      const fiat = entry[assetFiatField.value]
      if (fiat != null) tokenValue += fiat
    }
    // Only combine QUBIC value + token value once BOTH are known — otherwise
    // a slow-loading QUBIC price (fetched separately, see loadPortfolioData)
    // would make the total look smaller than the token value alone.
    const totalFiat = g.hasValue ? g.totalValue + tokenValue : null
    return {
      ...g,
      tokenValue,
      hasTokens,
      tokens: [...tokenCounts.entries()]
        .map(([name, v]) => ({ name, units: v.units, kind: v.kind }))
        .sort((a, b) => a.name.localeCompare(b.name)),
      totalFiat,
      hasTotalFiat: totalFiat != null,
    }
  })
})

const selectedAssetGroup = computed(() =>
  ownerAssetGroups.value.find(g => g.owner === selectedPortfolioOwner.value) || null
)

const assetsGrandTotal = computed(() => {
  let tokenValue = 0
  const kinds = new Set()
  for (const g of ownerAssetGroups.value) {
    tokenValue += g.tokenValue
    for (const tok of g.tokens) kinds.add(tok.name)
  }
  return {
    tokenValue,
    kinds: kinds.size,
    total: grandTotal.value.hasValue ? grandTotal.value.value + tokenValue : null,
  }
})

function fmtUnits(n) {
  if (n == null) return '—'
  if (store.hideAddresses) return '••••••'
  return Number(n).toLocaleString(store.locale)
}

function fmtTokenPrice(n) {
  if (n == null) return '—'
  if (store.hideAddresses) return '••••••'
  return Number(n).toLocaleString(store.locale, { maximumFractionDigits: 4 })
}

// Amber = share (issued by the QX smart contract itself), sky = token
// (issued by any other project/identity).
function assetKindChipClass(kind) {
  return kind === 'share'
    ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
    : 'bg-sky-500/10 text-sky-300 border-sky-500/20'
}

onMounted(async () => {
  await reload()
  loadPortfolioData()
})
</script>

<template>
  <div class="space-y-3">
  <PageHeader :title="t('nav.wallets')"
              :hint="activeTab === 'portfolio' ? t('wallet.tab_portfolio') : t('wallet.tab_config')">
    <div v-if="activeTab === 'config'" class="filter-row">
      <button :class="['filter-pill', store.walletFilter === 'all'      && 'filter-pill-active']"
              @click="store.walletFilter = 'all'">{{ t('filter.all') }}</button>
      <button :class="['filter-pill', store.walletFilter === 'private'  && 'filter-pill-active']"
              @click="store.walletFilter = 'private'">{{ t('filter.private') }}</button>
      <button :class="['filter-pill', store.walletFilter === 'business' && 'filter-pill-active']"
              @click="store.walletFilter = 'business'">{{ t('filter.business') }}</button>
    </div>
    <div class="tab-group">
      <button :class="['tab-btn', activeTab === 'portfolio' && 'tab-btn-active']"
              @click="setActiveTab('portfolio')">{{ t('wallet.tab_portfolio') }}</button>
      <button :class="['tab-btn', activeTab === 'config' && 'tab-btn-active']"
              @click="setActiveTab('config')">{{ t('wallet.tab_config') }}</button>
    </div>
  </PageHeader>

  <!-- Back button directly under the heading (only in portfolio drilldown) -->
  <div v-if="activeTab === 'portfolio' && selectedPortfolioOwner && selectedGroup" class="!mt-1">
    <BackButton :label="t('common.back')" @click="backToOwners" />
  </div>

  <PageLoader v-if="loading" />

  <template v-else>

    <!-- =================== PORTFOLIO TAB =================== -->
    <div v-if="activeTab === 'portfolio'" class="space-y-3">
      <!-- Filter pills + view switch + Add Wallet button -->
      <div class="flex items-center justify-between gap-2 flex-wrap">
        <div class="flex items-center gap-3 flex-wrap">
          <div class="filter-row">
            <button :class="['filter-pill', store.walletFilter === 'all'      && 'filter-pill-active']"
                    @click="store.walletFilter = 'all'">{{ t('filter.all') }}</button>
            <button :class="['filter-pill', store.walletFilter === 'private'  && 'filter-pill-active']"
                    @click="store.walletFilter = 'private'">{{ t('filter.private') }}</button>
            <button :class="['filter-pill', store.walletFilter === 'business' && 'filter-pill-active']"
                    @click="store.walletFilter = 'business'">{{ t('filter.business') }}</button>
          </div>
          <!-- View switch: QUBIC balances vs. token/share holdings -->
          <div class="tab-group">
            <button :class="['tab-btn', portfolioView === 'qubic' && 'tab-btn-active']"
                    @click="setPortfolioView('qubic')">QUBIC</button>
            <button :class="['tab-btn', portfolioView === 'assets' && 'tab-btn-active']"
                    @click="setPortfolioView('assets')">{{ t('wallet.view_assets') }}</button>
          </div>
        </div>
        <button class="btn text-sm" @click="showForm = !showForm">+ {{ t('wallet.add') }}</button>
      </div>

      <!-- Add-Form (shared, shown in both tabs) -->
      <div v-if="showForm" class="card space-y-3">
        <input v-model="form.id"    :placeholder="t('wallet.address')" class="input w-full font-mono text-xs" />
        <input v-model="form.label" :placeholder="t('wallet.label')"   class="input w-full text-xs" />
        <input v-model="form.owner" :placeholder="t('wallet.owner')"   class="input w-full text-xs"
               list="owner-list-add-portfolio" autocomplete="off" />
        <datalist id="owner-list-add-portfolio">
          <option v-for="o in uniqueOwners" :key="o" :value="o" />
        </datalist>
        <input v-model="form.note"  :placeholder="t('wallet.note')"    class="input w-full text-xs" />
        <select v-model="form.wallet_type" class="input w-full text-xs">
          <option value="PRIVATE">PRIVATE</option>
          <option value="BUSINESS">BUSINESS</option>
        </select>
        <input v-model="form.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
               list="function-list-add-portfolio" autocomplete="off" />
        <datalist id="function-list-add-portfolio">
          <option v-for="f in uniqueFunctions" :key="f" :value="f" />
        </datalist>
        <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
        <div class="flex gap-2">
          <button class="btn text-sm" @click="submit">{{ t('common.save') }}</button>
          <button class="btn-ghost text-sm" @click="showForm = false; error = ''">{{ t('common.cancel') }}</button>
        </div>
      </div>

      <div v-if="!ownerGroups.length" class="card p-6 text-center text-gray-500 text-xs">{{ t('wallet.none') }}</div>

      <template v-if="portfolioView === 'qubic'">
      <!-- Grand total summary bar (icon + colored label per column, like Dashboard panels) -->
      <div v-if="ownerGroups.length" class="card p-4 bg-gradient-to-r from-qubic-teal/5 to-qubic-teal/[0.02] border-qubic-teal/20">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 divide-y md:divide-y-0 md:divide-x divide-qubic-border/50">
          <!-- Portfolio Total QUBIC -->
          <div class="md:pl-0 pb-3 md:pb-0 min-w-0">
            <div class="flex items-center gap-1 mb-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-qubic-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
              </svg>
              <span class="text-xs uppercase tracking-wide text-qubic-teal">{{ t('wallet.portfolio_total') }} QUBIC</span>
            </div>
            <div class="font-mono text-base sm:text-xl whitespace-nowrap" :class="store.hideAddresses ? 'text-gray-500' : 'text-qubic-teal'">
              {{ store.hideAddresses ? '••••••' : grandTotal.balance.toLocaleString(store.locale) }}
            </div>
          </div>

          <!-- Current value -->
          <div v-if="grandTotal.hasValue" class="md:pl-4 pb-3 md:pb-0 min-w-0">
            <div class="flex items-center gap-1 mb-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
              </svg>
              <span class="text-xs uppercase tracking-wide text-emerald-400">{{ t('wallet.value') }}</span>
            </div>
            <div class="font-mono text-base sm:text-xl text-emerald-400 whitespace-nowrap" :title="fmtFiatAlt(grandTotal.value)">{{ fmtFiat(grandTotal.value) }}</div>
          </div>

          <!-- Unrealized P&L -->
          <div v-if="grandTotal.hasCost" class="md:pl-4 pb-3 md:pb-0 min-w-0">
            <div class="flex items-center gap-1 mb-1">
              <svg xmlns="http://www.w3.org/2000/svg"
                   :class="['w-3 h-3 flex-shrink-0', (grandTotal.value - grandTotal.cost) >= 0 ? 'text-green-400' : 'text-red-400']"
                   fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
              </svg>
              <span class="text-xs uppercase tracking-wide"
                    :class="(grandTotal.value - grandTotal.cost) >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ t('wallet.pnl_unrealized') }}
              </span>
            </div>
            <div class="font-mono text-base sm:text-xl whitespace-nowrap" :class="(grandTotal.value - grandTotal.cost) >= 0 ? 'text-green-400' : 'text-red-400'" :title="fmtFiatAlt(grandTotal.value - grandTotal.cost)">
              {{ (grandTotal.value - grandTotal.cost) >= 0 ? '+' : '' }}{{ fmtFiat(grandTotal.value - grandTotal.cost) }}
              <span class="text-xs font-normal"
                    :class="(grandTotal.value - grandTotal.cost) >= 0 ? 'text-green-400/80' : 'text-red-400/80'">
                {{ fmtPct((grandTotal.value - grandTotal.cost) / grandTotal.cost * 100) }}
              </span>
            </div>
          </div>

          <!-- Current price -->
          <div v-if="unitPrice != null" class="md:pl-4 min-w-0">
            <div class="flex items-center gap-1 mb-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
              </svg>
              <span class="text-xs uppercase tracking-wide text-sky-400">{{ t('wallet.current_price') }}</span>
            </div>
            <div class="font-mono text-base sm:text-xl text-sky-400 whitespace-nowrap cursor-copy select-none"
                 :title="unitPriceAlt != null ? fmtRateLocale(unitPriceAlt) + altFiatSymbol : undefined"
                 @dblclick.prevent="copyValue(unitPrice)">
              {{ fmtRateLocale(unitPrice) }}{{ fiatSymbol }}
            </div>
          </div>
        </div>
      </div>

      <!-- View A: Owner panel grid (no owner selected) -->
      <div v-if="!selectedPortfolioOwner && ownerGroups.length"
           class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <button v-for="group in ownerGroups" :key="group.owner"
                class="card !p-3 text-left transition-all hover:border-qubic-teal/50 hover:shadow-lg hover:shadow-qubic-teal/10 group cq-panel"
                @click="selectPortfolioOwner(group.owner)">
          <!-- Header: owner + wallet count badge -->
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="flex items-center gap-1.5 min-w-0 flex-1">
              <OwnerIcon :type="groupIconType(group)" />
              <span class="font-medium text-sm truncate group-hover:text-qubic-teal transition-colors">
                {{ store.hideAddresses ? '••••••' : group.owner }}
              </span>
            </div>
            <span class="text-xs px-2 py-0.5 rounded-md bg-qubic-teal/10 text-qubic-teal border border-qubic-teal/20 font-mono shrink-0">
              {{ group.wallets.length }}w
            </span>
          </div>

          <!-- Balance (hero value) -->
          <div class="font-mono text-lg mb-1 whitespace-nowrap" :class="group.hasNullBalance ? 'text-gray-500 italic' : 'text-gray-200'">
            {{ store.hideAddresses ? '••••••' : group.totalBalance.toLocaleString(store.locale) }}
            <span class="text-sm text-gray-500 ml-0.5">QUBIC</span>
          </div>

          <!-- Fiat value -->
          <div v-if="group.hasValue" class="font-mono text-sm text-gray-400 mb-0.5 whitespace-nowrap" :title="fmtFiatAlt(group.totalValue)">
            {{ fmtFiat(group.totalValue) }}
          </div>

          <!-- P&L row -->
          <div v-if="group.hasCost" class="flex items-baseline gap-2 mt-1 flex-wrap">
            <span class="font-mono text-sm font-semibold whitespace-nowrap"
                  :class="(group.totalValue - group.totalCost) >= 0 ? 'text-green-400' : 'text-red-400'">
              {{ (group.totalValue - group.totalCost) >= 0 ? '▲' : '▼' }}
              {{ fmtPct((group.totalValue - group.totalCost) / group.totalCost * 100) }}
            </span>
            <span class="font-mono text-xs whitespace-nowrap"
                  :class="(group.totalValue - group.totalCost) >= 0 ? 'text-green-400/80' : 'text-red-400/80'"
                  :title="fmtFiatAlt(group.totalValue - group.totalCost)">
              {{ (group.totalValue - group.totalCost) >= 0 ? '+' : '' }}{{ fmtFiat(group.totalValue - group.totalCost) }}
            </span>
          </div>

          <!-- Footer: events + type pills -->
          <div class="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-qubic-border/30">
            <span class="text-xs text-gray-500 font-mono">
              {{ group.totalEvents.toLocaleString(store.locale) }} {{ t('wallet.entries') }}
            </span>
            <div class="flex gap-1">
              <span v-for="type in [...group.types]" :key="type"
                    :class="['pill text-xs py-0.5 px-2', type === 'BUSINESS' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' : '']">
                {{ type }}
              </span>
            </div>
          </div>
        </button>
      </div>

      <!-- View B: Wallet list for selected owner -->
      <div v-if="selectedPortfolioOwner && selectedGroup">
        <!-- Owner summary -->
        <div class="flex items-center justify-end gap-3 mb-3 flex-wrap">
          <div class="flex items-center gap-4 flex-wrap">
            <div>
              <div class="text-xs text-gray-500">{{ t('filter.owner') }}</div>
              <div class="font-medium flex items-center gap-1.5">
                <OwnerIcon :type="groupIconType(selectedGroup)" />
                {{ store.hideAddresses ? '••••••' : selectedGroup.owner }}
              </div>
            </div>
            <div class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.balance') }}</div>
              <div class="font-mono text-sm">
                {{ store.hideAddresses ? '••••••' : selectedGroup.totalBalance.toLocaleString(store.locale) }}<span class="ml-0.5 text-gray-500">QUBIC</span>
              </div>
            </div>
            <div v-if="selectedGroup.hasValue" class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.value') }}</div>
              <div class="font-mono text-sm" :title="fmtFiatAlt(selectedGroup.totalValue)">{{ fmtFiat(selectedGroup.totalValue) }}</div>
            </div>
            <div v-if="selectedGroup.hasCost" class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.pnl') }}</div>
              <div class="font-mono text-sm" :class="(selectedGroup.totalValue - selectedGroup.totalCost) >= 0 ? 'text-green-400' : 'text-red-400'" :title="fmtFiatAlt(selectedGroup.totalValue - selectedGroup.totalCost)">
                {{ (selectedGroup.totalValue - selectedGroup.totalCost) >= 0 ? '+' : '' }}{{ fmtFiat(selectedGroup.totalValue - selectedGroup.totalCost) }}
                <span class="text-xs">{{ fmtPct((selectedGroup.totalValue - selectedGroup.totalCost) / selectedGroup.totalCost * 100) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Wallet list -->
        <div class="card overflow-hidden">
          <!-- Mobile -->
          <div class="sm:hidden divide-y divide-qubic-border/20">
            <router-link v-for="w in selectedGroup.wallets" :key="w.id" :to="`/wallets/${w.id}`"
                         class="flex items-center justify-between gap-2 px-4 py-2.5 hover:bg-white/[0.02] group">
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors flex items-center gap-1.5">
                  <OwnerIcon :type="w.wallet_type" size="w-3.5 h-3.5" />
                  {{ maskLabel(w.label, w.id) }}
                </div>
                <div class="text-xs font-mono text-gray-500 truncate">{{ store.hideAddresses ? '••••••••••••' : w.id }}</div>
                <div class="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span class="text-xs font-mono" :class="w.balance == null ? 'text-gray-600 italic' : 'text-gray-400'">{{ fmtBalance(w) }}<span class="ml-0.5 text-gray-500">QUBIC</span></span><span v-if="w.balance != null" :class="['text-xs ml-0.5', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
                  <span v-if="walletValue(w) != null" class="text-xs font-mono text-gray-400" :title="fmtFiatAlt(walletValue(w))">· {{ fmtFiat(walletValue(w)) }}</span>
                  <span v-if="walletPnl(w) != null" class="text-xs font-mono"
                        :class="walletPnl(w) >= 0 ? 'text-green-400' : 'text-red-400'"
                        :title="fmtFiatAlt(walletPnl(w))">
                    {{ walletPnl(w) >= 0 ? '+' : '' }}{{ fmtFiat(walletPnl(w)) }} ({{ fmtPct(walletPnlPct(w)) }})
                  </span>
                  <span v-if="w.function" class="text-xs text-gray-500">· {{ w.function }}</span>
                </div>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <span :class="['pill text-xs', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">{{ w.wallet_type }}</span>
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
              </div>
            </router-link>
          </div>
          <!-- Desktop table -->
          <table class="table-std hidden sm:table">
            <thead class="thead-std">
              <tr>
                <th class="th">{{ t('wallet.label') }}</th>
                <th class="th hidden md:table-cell">{{ t('wallet.address') }}</th>
                <th class="th">{{ t('wallet.type') }}</th>
                <th class="th-right whitespace-nowrap">{{ t('wallet.balance') }} QUBIC</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.value') }}</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.pnl') }}</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.entries') }}</th>
                <th class="th-right" :title="t('walletDetail.entries')"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in selectedGroup.wallets" :key="w.id" class="tr-row cursor-pointer hover:bg-white/[0.03] transition-colors group" @click="goToWallet(w.id)">
                <td class="td">
                  <div class="flex items-center gap-1.5 font-medium group-hover:text-qubic-teal transition-colors">
                    <OwnerIcon :type="w.wallet_type" size="w-3.5 h-3.5" />
                    <span>
                      {{ maskLabel(w.label, w.id) }}
                      <span v-if="w.function" class="text-xs text-gray-500 font-normal ml-1">· {{ w.function }}</span>
                    </span>
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                  </div>
                </td>
                <td class="td hidden md:table-cell">
                  <div class="flex items-center gap-2 font-mono text-xs text-gray-400">
                    <span :title="store.hideAddresses ? '' : w.id">{{ store.hideAddresses ? '••••••••••••' : w.id.slice(0,5) + '…' + w.id.slice(-5) }}</span>
                    <button v-if="!store.hideAddresses" @click.stop="copyAddress(w.id)" class="icon-btn" :title="t('assets.copy')">
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                    <a :href="explorerUrl(w.id)" target="_blank" rel="noopener" class="icon-btn" :title="t('assets.explorer')" @click.stop>
                      <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>
                  </div>
                </td>
                <td class="td">
                  <span :class="['pill text-xs', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">{{ w.wallet_type }}</span>
                </td>
                <td class="td text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <span class="font-mono text-xs whitespace-nowrap cursor-copy select-none"
                          :class="w.balance == null ? 'text-gray-500 italic' : 'text-gray-300'"
                          @dblclick.prevent.stop="w.balance != null && copyValue(w.balance)">{{ fmtBalance(w) }}</span>
                    <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
                  </div>
                </td>
                <td class="td text-right hidden lg:table-cell font-mono text-xs whitespace-nowrap">
                  <span v-if="walletValue(w) != null" class="text-gray-300 cursor-copy select-none"
                        :title="fmtFiatAlt(walletValue(w))"
                        @dblclick.prevent.stop="copyValue(walletValue(w))">{{ fmtFiat(walletValue(w)) }}</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="td text-right hidden lg:table-cell font-mono text-xs whitespace-nowrap">
                  <template v-if="walletPnl(w) != null">
                    <div :class="walletPnl(w) >= 0 ? 'text-green-400 cursor-copy select-none' : 'text-red-400 cursor-copy select-none'"
                         :title="fmtFiatAlt(walletPnl(w))"
                         @dblclick.prevent.stop="copyValue(walletPnl(w))">
                      {{ walletPnl(w) >= 0 ? '+' : '' }}{{ fmtFiat(walletPnl(w)) }}
                    </div>
                    <div class="text-xs" :class="walletPnl(w) >= 0 ? 'text-green-400/70' : 'text-red-400/70'">
                      {{ fmtPct(walletPnlPct(w)) }}
                    </div>
                  </template>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="td text-right hidden lg:table-cell font-mono text-xs text-gray-400">
                  {{ w.total_events != null ? w.total_events.toLocaleString(store.locale) : '—' }}
                </td>
                <td class="td text-right">
                  <router-link :to="`/wallets/${w.id}`" class="icon-btn" :title="t('walletDetail.entries')" @click.stop>
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"/>
                    </svg>
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </template>

      <!-- =================== TOKEN/SHARES VIEW =================== -->
      <template v-else>
        <!-- Loading -->
        <div v-if="assetsLoading" class="card flex items-center justify-center py-10">
          <div class="flex items-center gap-3 text-sm text-gray-400">
            <div class="w-5 h-5 rounded-full border-2 border-qubic-border border-t-qubic-teal animate-spin" />
            {{ t('wallet.assets_loading') }}
          </div>
        </div>

        <template v-else>
          <!-- Token grand total summary bar -->
          <div v-if="ownerGroups.length" class="card p-4 bg-gradient-to-r from-violet-500/5 to-violet-500/[0.02] border-violet-500/20">
            <div class="grid grid-cols-2 md:grid-cols-3 gap-4 divide-y md:divide-y-0 md:divide-x divide-qubic-border/50">
              <!-- Token value -->
              <div class="md:pl-0 pb-3 md:pb-0 min-w-0">
                <div class="flex items-center gap-1 mb-1">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
                  </svg>
                  <span class="text-xs uppercase tracking-wide text-violet-400">{{ t('wallet.token_value') }}</span>
                </div>
                <div class="font-mono text-base sm:text-xl text-violet-400 whitespace-nowrap cursor-copy select-none"
                     @dblclick.prevent="copyValue(assetsGrandTotal.tokenValue)">{{ fmtFiat(assetsGrandTotal.tokenValue) }}</div>
              </div>
              <!-- Token kinds -->
              <div class="md:pl-4 pb-3 md:pb-0 min-w-0">
                <div class="flex items-center gap-1 mb-1">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h10M7 12h10M7 17h6"/>
                  </svg>
                  <span class="text-xs uppercase tracking-wide text-gray-400">{{ t('wallet.token_kinds') }}</span>
                </div>
                <div class="font-mono text-base sm:text-xl text-gray-300 whitespace-nowrap">{{ assetsGrandTotal.kinds }}</div>
              </div>
              <!-- Total incl. QUBIC -->
              <div class="md:pl-4 min-w-0">
                <div class="flex items-center gap-1 mb-1">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
                  </svg>
                  <span class="text-xs uppercase tracking-wide text-emerald-400">{{ t('wallet.total_incl_qu') }}</span>
                </div>
                <div class="font-mono text-base sm:text-xl text-emerald-400 whitespace-nowrap cursor-copy select-none"
                     @dblclick.prevent="copyValue(assetsGrandTotal.total)">{{ fmtFiat(assetsGrandTotal.total) }}</div>
              </div>
            </div>
          </div>

          <!-- View A: owner cards (token perspective) -->
          <div v-if="!selectedPortfolioOwner && ownerAssetGroups.length"
               class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            <button v-for="group in ownerAssetGroups" :key="group.owner"
                    class="card !p-3 text-left transition-all hover:border-violet-400/50 hover:shadow-lg hover:shadow-violet-500/10 group cq-panel"
                    @click="selectPortfolioOwner(group.owner)">
              <div class="flex items-start justify-between gap-2 mb-2">
                <div class="flex items-center gap-1.5 min-w-0 flex-1">
                  <OwnerIcon :type="groupIconType(group)" />
                  <span class="font-medium text-sm truncate group-hover:text-violet-300 transition-colors">
                    {{ store.hideAddresses ? '••••••' : group.owner }}
                  </span>
                </div>
                <span class="text-xs px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-300 border border-violet-500/20 font-mono shrink-0">
                  {{ group.wallets.length }}w
                </span>
              </div>

              <!-- Total value (hero) — the one number that matters: tokens + QUBIC -->
              <div class="font-mono text-lg mb-2 whitespace-nowrap" :class="group.hasTotalFiat ? 'text-emerald-400' : 'text-gray-600'">
                <template v-if="group.hasTotalFiat">{{ fmtFiat(group.totalFiat) }}</template>
                <template v-else>{{ t('wallet.no_assets') }}</template>
              </div>

              <!-- Token chips — all of them, sorted by name; the card simply grows.
                   Amber = share (issued by the QX contract), sky = token. -->
              <div v-if="group.tokens.length" class="flex flex-wrap gap-1 mb-1">
                <span v-for="tok in group.tokens" :key="tok.name"
                      :class="['pill text-xs py-0.5 px-2 font-mono', assetKindChipClass(tok.kind)]">
                  {{ tok.name }} {{ fmtUnits(tok.units) }}
                </span>
              </div>

              <div class="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-qubic-border/30">
                <span class="text-xs text-gray-500 font-mono">
                  {{ group.tokens.length }} {{ t('wallet.token_kinds') }}
                </span>
                <div class="flex gap-1">
                  <span v-for="type in [...group.types]" :key="type"
                        :class="['pill text-xs py-0.5 px-2', type === 'BUSINESS' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' : '']">
                    {{ type }}
                  </span>
                </div>
              </div>
            </button>
          </div>

          <!-- View B: per-wallet token drilldown for selected owner -->
          <div v-if="selectedPortfolioOwner && selectedAssetGroup" class="space-y-3">
            <!-- Owner summary -->
            <div class="flex items-center justify-end gap-4 flex-wrap">
              <div>
                <div class="text-xs text-gray-500">{{ t('filter.owner') }}</div>
                <div class="font-medium flex items-center gap-1.5">
                  <OwnerIcon :type="groupIconType(selectedAssetGroup)" />
                  {{ store.hideAddresses ? '••••••' : selectedAssetGroup.owner }}
                </div>
              </div>
              <div class="text-right">
                <div class="text-xs text-gray-500">{{ t('wallet.token_value') }}</div>
                <div class="font-mono text-sm text-violet-300">{{ fmtFiat(selectedAssetGroup.tokenValue) }}</div>
              </div>
              <div class="text-right">
                <div class="text-xs text-gray-500">{{ t('wallet.total_incl_qu') }}</div>
                <div class="font-mono text-sm text-emerald-400">{{ fmtFiat(selectedAssetGroup.totalFiat) }}</div>
              </div>
            </div>

            <!-- One card per wallet -->
            <div v-for="w in selectedAssetGroup.wallets" :key="w.id" class="card">
              <div class="flex items-start justify-between gap-3 flex-wrap mb-2">
                <router-link :to="`/wallets/${w.id}`" class="flex items-center gap-1.5 min-w-0 group">
                  <OwnerIcon :type="w.wallet_type" size="w-3.5 h-3.5" />
                  <span class="font-medium text-sm group-hover:text-qubic-teal transition-colors">{{ maskLabel(w.label, w.id) }}</span>
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                </router-link>
                <div class="flex items-center gap-4 text-right flex-wrap">
                  <div>
                    <div class="text-xs text-gray-500">QUBIC</div>
                    <div class="font-mono text-xs text-gray-300">{{ fmtBalance(w) }}</div>
                  </div>
                  <div v-if="walletValue(w) != null">
                    <div class="text-xs text-gray-500">{{ t('wallet.value') }} QUBIC</div>
                    <div class="font-mono text-xs text-gray-300">{{ fmtFiat(walletValue(w)) }}</div>
                  </div>
                  <div v-if="walletAssetsFiat(w) != null">
                    <div class="text-xs text-gray-500">{{ t('wallet.token_value') }}</div>
                    <div class="font-mono text-xs text-violet-300">{{ fmtFiat(walletAssetsFiat(w)) }}</div>
                  </div>
                  <div v-if="walletTotalFiat(w) != null">
                    <div class="text-xs text-gray-500">{{ t('wallet.total_short') }}</div>
                    <div class="font-mono text-sm font-semibold text-emerald-400 cursor-copy select-none"
                         @dblclick.prevent="copyValue(walletTotalFiat(w))">{{ fmtFiat(walletTotalFiat(w)) }}</div>
                  </div>
                </div>
              </div>

              <!-- Asset table -->
              <div v-if="walletAssets(w).length" class="overflow-x-auto">
                <table class="table-std">
                  <thead>
                    <tr class="border-b border-qubic-border text-gray-500 uppercase">
                      <th class="text-left py-2 pr-3">{{ t('assets.name') }}</th>
                      <th class="text-left py-2 pr-3">{{ t('walletDetail.assets_kind') }}</th>
                      <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('walletDetail.assets_units') }}</th>
                      <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('walletDetail.assets_price') }}</th>
                      <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('walletDetail.assets_value_qu') }}</th>
                      <th class="text-right py-2 whitespace-nowrap">{{ t('walletDetail.assets_value') }} {{ store.currency }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(a, i) in walletAssets(w)" :key="i"
                        class="border-b border-qubic-border/30 hover:bg-violet-500/5 transition-colors">
                      <td class="py-2 pr-3 font-medium text-gray-200">
                        {{ a.name }}
                        <span v-if="a.issuer_label" class="text-xs text-gray-500 font-normal ml-1">· {{ a.issuer_label }}</span>
                      </td>
                      <td class="py-2 pr-3">
                        <span :class="['pill text-xs py-0.5 px-2', assetKindChipClass(a.kind)]">
                          {{ a.kind === 'share' ? t('walletDetail.assets_share') : t('walletDetail.assets_token') }}
                        </span>
                      </td>
                      <td class="py-2 pr-3 text-right font-mono cursor-copy select-none"
                          @dblclick.prevent="copyValue(a.units)">{{ fmtUnits(a.units) }}</td>
                      <td class="py-2 pr-3 text-right font-mono text-gray-400">{{ fmtTokenPrice(a.price_qu) }}</td>
                      <td class="py-2 pr-3 text-right font-mono text-qubic-teal">{{ a.value_qubic != null ? fmtUnits(a.value_qubic) : '—' }}</td>
                      <td class="py-2 text-right font-mono text-green-400 cursor-copy select-none"
                          @dblclick.prevent="a[assetValueField] != null && copyValue(a[assetValueField])">
                        {{ a[assetValueField] != null ? fmtFiat(a[assetValueField]) : '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="text-xs text-gray-600">{{ t('wallet.no_assets') }}</p>
            </div>
          </div>
        </template>
      </template>
    </div>

    <!-- =================== KONFIGURATION TAB =================== -->
    <template v-else>

    <!-- Add button + owner filter pills -->
    <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
      <div v-if="uniqueOwners.length" class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-gray-500 uppercase tracking-wide">{{ t('filter.owner') }}:</span>
        <button v-for="owner in uniqueOwners" :key="owner"
                :class="['btn-ghost text-xs py-1 px-3 transition-colors flex items-center gap-1.5', selectedOwner === owner
                  ? 'bg-violet-500/20 border-violet-400 text-violet-300'
                  : 'text-gray-400 hover:bg-violet-500/10 hover:border-violet-400/60 hover:text-violet-300']"
                @click="selectedOwner = selectedOwner === owner ? null : owner">
          <OwnerIcon :type="ownerIconType(owner)" size="w-3 h-3" />
          {{ store.hideAddresses ? '••••••' : owner }}
        </button>
      </div>
      <div v-else></div>
      <button class="btn text-sm" @click="showForm = !showForm">+ {{ t('wallet.add') }}</button>
    </div>

  <!-- Add-Form -->
  <div v-if="showForm" class="card mb-4 space-y-3">
    <input v-model="form.id"    :placeholder="t('wallet.address')" class="input w-full font-mono text-xs" />
    <input v-model="form.label" :placeholder="t('wallet.label')"   class="input w-full text-xs" />
    <input v-model="form.owner" :placeholder="t('wallet.owner')"   class="input w-full text-xs"
           list="owner-list-add" autocomplete="off" />
    <datalist id="owner-list-add">
      <option v-for="o in uniqueOwners" :key="o" :value="o" />
    </datalist>
    <input v-model="form.note"  :placeholder="t('wallet.note')"    class="input w-full text-xs" />
    <select v-model="form.wallet_type" class="input w-full text-xs">
      <option value="PRIVATE">PRIVATE</option>
      <option value="BUSINESS">BUSINESS</option>
    </select>
    <input v-model="form.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
           list="function-list-add" autocomplete="off" />
    <datalist id="function-list-add">
      <option v-for="f in uniqueFunctions" :key="f" :value="f" />
    </datalist>
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <div class="flex gap-2">
      <button class="btn text-sm" @click="submit">{{ t('common.save') }}</button>
      <button class="btn-ghost text-sm" @click="showForm = false; error = ''">{{ t('common.cancel') }}</button>
    </div>
  </div>

  <!-- Mobile: card list -->
  <div class="sm:hidden space-y-2">
    <div v-if="!displayedWallets.length" class="card p-6 text-center text-gray-500 text-xs">
      {{ t('wallet.none') }}
    </div>
    <div v-for="w in displayedWallets" :key="w.id" class="card">
      <!-- Edit-Form (mobile) -->
      <div v-if="editingId === w.id" class="space-y-2 mb-2">
        <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
        <input v-model="editForm.owner" :placeholder="t('wallet.owner')" class="input w-full text-xs"
               list="owner-list-edit" autocomplete="off" />
        <datalist id="owner-list-edit">
          <option v-for="o in uniqueOwners" :key="o" :value="o" />
        </datalist>
        <input v-model="editForm.note"  :placeholder="t('wallet.note')"  class="input w-full text-xs" />
        <select v-model="editForm.wallet_type" class="input w-full text-xs">
          <option value="PRIVATE">PRIVATE</option>
          <option value="BUSINESS">BUSINESS</option>
        </select>
        <input v-model="editForm.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
               list="function-list-mobile-edit" autocomplete="off" />
        <datalist id="function-list-mobile-edit">
          <option v-for="f in uniqueFunctions" :key="f" :value="f" />
        </datalist>
        <p v-if="editError" class="text-red-400 text-xs">{{ editError }}</p>
        <div class="flex gap-2">
          <button class="btn text-sm" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
          <button class="btn-ghost text-sm" @click="cancelEdit">{{ t('common.cancel') }}</button>
        </div>
      </div>
      <div v-else class="flex items-center justify-between gap-2">
        <router-link :to="`/wallets/${w.id}`" class="flex items-center gap-2 min-w-0 flex-1 group">
          <div class="min-w-0">
            <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors flex items-center gap-1.5">
              <OwnerIcon :type="w.wallet_type" size="w-3.5 h-3.5" />
              {{ maskLabel(w.label, w.id) }}
            </div>
            <div class="text-xs font-mono text-gray-500 truncate">{{ store.hideAddresses ? '••••••••••••' : w.id }}</div>
            <div class="flex items-center gap-1 mt-0.5">
              <span class="text-xs font-mono" :class="w.balance == null ? 'text-gray-600 italic' : 'text-gray-400'">{{ fmtBalance(w) }}</span>
              <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
            </div>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-500 group-hover:text-qubic-teal flex-shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </router-link>
        <div class="flex items-center gap-2 flex-shrink-0">
          <span :class="['pill text-xs', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
            {{ w.wallet_type }}
          </span>
          <button v-if="!store.hideAddresses" @click="copyAddress(w.id)"
                  class="icon-btn" :title="t('assets.copy')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          <a :href="explorerUrl(w.id)" target="_blank" rel="noopener"
             class="icon-btn" :title="t('assets.explorer')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </a>
          <button @click="startEdit(w)" class="btn-action" :title="t('wallet.edit')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button @click="remove(w.id)" class="btn-delete" :title="t('wallet.delete')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Desktop: table -->
  <div class="card overflow-hidden hidden sm:block">
    <table class="table-std">
      <thead class="thead-std">
        <tr>
          <th class="th cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('label')">
            <span class="flex items-center gap-1">{{ t('wallet.label') }}<span class="opacity-50">{{ configSortKey === 'label' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th hidden md:table-cell cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('owner')">
            <span class="flex items-center gap-1">{{ t('wallet.owner') }}<span class="opacity-50">{{ configSortKey === 'owner' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('address')">
            <span class="flex items-center gap-1">{{ t('wallet.address') }}<span class="opacity-50">{{ configSortKey === 'address' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('type')">
            <span class="flex items-center gap-1">{{ t('wallet.type') }}<span class="opacity-50">{{ configSortKey === 'type' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th hidden md:table-cell cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('function')">
            <span class="flex items-center gap-1">{{ t('wallet.function') }}<span class="opacity-50">{{ configSortKey === 'function' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th hidden md:table-cell cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('note')">
            <span class="flex items-center gap-1">{{ t('wallet.note') }}<span class="opacity-50">{{ configSortKey === 'note' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span></span>
          </th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('balance')">
            <span class="flex items-center justify-end gap-1"><span class="opacity-50">{{ configSortKey === 'balance' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>{{ t('wallet.balance') }} QUBIC</span>
          </th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap cursor-pointer select-none hover:text-qubic-teal transition-colors" @click="toggleConfigSort('entries')">
            <span class="flex items-center justify-end gap-1"><span class="opacity-50">{{ configSortKey === 'entries' ? (configSortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>{{ t('wallet.entries') }}</span>
          </th>
          <th class="th-right">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!displayedWallets.length">
          <td colspan="9" class="text-center p-8 text-gray-500">{{ t('wallet.none') }}</td>
        </tr>
        <template v-for="w in displayedWallets" :key="w.id">
          <!-- Edit-Row -->
          <tr v-if="editingId === w.id" class="tr-edit">
            <td class="p-2">
              <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.owner" :placeholder="t('wallet.owner')" class="input w-full text-xs"
                     list="owner-list-desktop-edit" autocomplete="off" />
              <datalist id="owner-list-desktop-edit">
                <option v-for="o in uniqueOwners" :key="o" :value="o" />
              </datalist>
            </td>
            <td class="p-2 font-mono text-gray-500">
              {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0, 5) + '…' + w.id.slice(-5) }}
            </td>
            <td class="p-2">
              <select v-model="editForm.wallet_type" class="input text-xs">
                <option value="PRIVATE">PRIVATE</option>
                <option value="BUSINESS">BUSINESS</option>
              </select>
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
                     list="function-list-desktop-edit" autocomplete="off" />
              <datalist id="function-list-desktop-edit">
                <option v-for="f in uniqueFunctions" :key="f" :value="f" />
              </datalist>
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.note" :placeholder="t('wallet.note')" class="input w-full text-xs" />
            </td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 text-right">
              <p v-if="editError" class="text-red-400 text-xs text-right mb-1">{{ editError }}</p>
              <div class="flex justify-end gap-2">
                <button class="btn text-sm py-1" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
                <button class="btn-ghost text-sm py-1" @click="cancelEdit">{{ t('common.cancel') }}</button>
              </div>
            </td>
          </tr>
          <!-- Normal-Row -->
          <tr v-else class="tr-row cursor-pointer hover:bg-white/[0.03] transition-colors group" @click="goToWallet(w.id)">
            <td class="td">
              <div class="flex items-center gap-1.5 font-medium group-hover:text-qubic-teal transition-colors">
                <OwnerIcon :type="w.wallet_type" size="w-3.5 h-3.5" />
                {{ maskLabel(w.label, w.id) }}
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>
            </td>
            <td class="td text-gray-400 hidden md:table-cell">
              <div v-if="w.owner" class="flex items-center gap-1.5">
                <OwnerIcon :type="w.wallet_type" size="w-3 h-3" />
                <span>{{ store.hideAddresses ? '••••••' : w.owner }}</span>
              </div>
              <span v-else>—</span>
            </td>
            <td class="td">
              <div class="flex items-center gap-2 font-mono text-gray-400">
                <span :title="store.hideAddresses ? '' : w.id">
                  {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0, 5) + '…' + w.id.slice(-5) }}
                </span>
                <button v-if="!store.hideAddresses" @click.stop="copyAddress(w.id)"
                        class="icon-btn" :title="t('assets.copy')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
                <a :href="explorerUrl(w.id)" target="_blank" rel="noopener"
                   class="icon-btn" :title="t('assets.explorer')" @click.stop>
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              </div>
            </td>
            <td class="td">
              <span :class="['pill', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
                {{ w.wallet_type }}
              </span>
            </td>
            <td class="td text-gray-400 hidden md:table-cell">{{ w.function || '—' }}</td>
            <td class="td text-gray-400 hidden md:table-cell">{{ w.note || '—' }}</td>
            <td class="td hidden lg:table-cell text-right">
              <div class="flex items-center justify-end gap-1.5">
                <span class="font-mono whitespace-nowrap" :class="w.balance == null ? 'text-gray-500 italic' : 'text-gray-300'">
                  {{ fmtBalance(w) }}
                </span>
                <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
              </div>
            </td>
            <td class="td hidden lg:table-cell text-right font-mono text-gray-400">
              {{ w.total_events != null ? w.total_events.toLocaleString(store.locale) : '—' }}
            </td>
            <td class="td text-right">
              <div class="flex justify-end gap-3">
                <button @click.stop="startEdit(w)" class="btn-action" :title="t('wallet.edit')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button @click.stop="remove(w.id)" class="btn-delete" :title="t('wallet.delete')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
    </template><!-- end config tab -->
  </template>
  </div>
</template>
