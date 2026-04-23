<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'
import { useQubicUtils } from '../composables/useQubicUtils'

const store = useAppStore()
const { t } = useTranslation()
const { explorerUrl, copyAddress, maskLabel } = useQubicUtils()
const router = useRouter()
const route = useRoute()

function goToWallet(id) { router.push(`/wallets/${id}`) }
const showForm      = ref(false)
const loading       = ref(true)
const editingId     = ref(null)
const error         = ref('')
const editError     = ref('')
const selectedOwner = ref(null)
const form          = ref({ id: '', label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })
const editForm      = ref({ label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })

const uniqueOwners = computed(() =>
  [...new Set(store.wallets.map(w => w.owner).filter(Boolean))].sort()
)

const uniqueFunctions = computed(() =>
  [...new Set(store.wallets.map(w => w.function).filter(Boolean))].sort()
)

const displayedWallets = computed(() => {
  const base = Array.isArray(store.filteredWallets) ? store.filteredWallets : []
  if (!selectedOwner.value) return base
  return base.filter(w => w && w.owner === selectedOwner.value)
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

// Tabs & Portfolio selection — synced to URL query (?tab=, ?owner=)
const activeTab = ref(route.query.tab === 'config' ? 'config' : 'portfolio')
const selectedPortfolioOwner = ref(route.query.owner || null)

watch(() => route.query, (q) => {
  activeTab.value = q.tab === 'config' ? 'config' : 'portfolio'
  selectedPortfolioOwner.value = q.owner || null
})

function setActiveTab(tab) {
  const q = {}
  if (tab === 'config') q.tab = 'config'
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

function fmtFiat(n) {
  if (n == null) return '—'
  if (store.hideAddresses) return '••••••'
  return `${fiatSymbol.value}${n.toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
  return [...map.values()].sort((a, b) => {
    if (a.owner === '—') return 1
    if (b.owner === '—') return -1
    return a.owner.localeCompare(b.owner)
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

onMounted(async () => {
  await reload()
  loadPortfolioData()
})
</script>

<template>
  <!-- Top bar: type filter + tab switcher -->
  <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
    <div class="flex gap-2 flex-wrap">
      <button :class="['btn-ghost text-sm', store.walletFilter === 'all'      && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'all'">{{ t('filter.all') }}</button>
      <button :class="['btn-ghost text-sm', store.walletFilter === 'private'  && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'private'">{{ t('filter.private') }}</button>
      <button :class="['btn-ghost text-sm', store.walletFilter === 'business' && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'business'">{{ t('filter.business') }}</button>
    </div>
    <div class="flex gap-0.5 bg-qubic-surface border border-qubic-border rounded-lg p-0.5">
      <button :class="['btn-ghost text-sm py-1 px-3 border-0 rounded-md transition-all', activeTab === 'portfolio' && 'bg-qubic-teal/20 text-qubic-teal']"
              @click="setActiveTab('portfolio')">{{ t('wallet.tab_portfolio') }}</button>
      <button :class="['btn-ghost text-sm py-1 px-3 border-0 rounded-md transition-all', activeTab === 'config' && 'bg-qubic-teal/20 text-qubic-teal']"
              @click="setActiveTab('config')">{{ t('wallet.tab_config') }}</button>
    </div>
  </div>

  <PageLoader v-if="loading" />

  <template v-else>

    <!-- =================== PORTFOLIO TAB =================== -->
    <div v-if="activeTab === 'portfolio'" class="space-y-3">
      <div v-if="!ownerGroups.length" class="card p-6 text-center text-gray-500 text-xs">{{ t('wallet.none') }}</div>

      <!-- Grand total summary bar -->
      <div v-if="ownerGroups.length" class="card p-4 bg-gradient-to-r from-qubic-teal/5 to-qubic-teal/[0.02] border-qubic-teal/20">
        <div class="flex items-center flex-wrap gap-6">
          <div class="flex-1 min-w-[140px]">
            <div class="text-[10px] uppercase tracking-wide text-gray-500">{{ t('wallet.portfolio_total') }}</div>
            <div class="font-mono text-lg" :class="store.hideAddresses ? 'text-gray-500' : 'text-gray-200'">
              {{ store.hideAddresses ? '••••••' : grandTotal.balance.toLocaleString(store.locale) }} QU
            </div>
          </div>
          <div v-if="grandTotal.hasValue" class="min-w-[120px]">
            <div class="text-[10px] uppercase tracking-wide text-gray-500">{{ t('wallet.value') }}</div>
            <div class="font-mono text-lg">{{ fmtFiat(grandTotal.value) }}</div>
          </div>
          <div v-if="grandTotal.hasCost" class="min-w-[140px]">
            <div class="text-[10px] uppercase tracking-wide text-gray-500">{{ t('wallet.pnl_unrealized') }}</div>
            <div class="font-mono text-lg" :class="(grandTotal.value - grandTotal.cost) >= 0 ? 'text-green-400' : 'text-red-400'">
              {{ (grandTotal.value - grandTotal.cost) >= 0 ? '+' : '' }}{{ fmtFiat(grandTotal.value - grandTotal.cost) }}
              <span class="text-xs">{{ fmtPct((grandTotal.value - grandTotal.cost) / grandTotal.cost * 100) }}</span>
            </div>
          </div>
          <div v-if="unitPrice != null" class="text-xs text-gray-500 leading-tight">
            <div>{{ t('wallet.current_price') }}</div>
            <div class="font-mono text-gray-400">{{ fiatSymbol }}{{ unitPrice.toFixed(8) }}</div>
          </div>
        </div>
      </div>

      <!-- View A: Owner panel grid (no owner selected) -->
      <div v-if="!selectedPortfolioOwner && ownerGroups.length"
           class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <button v-for="group in ownerGroups" :key="group.owner"
                class="card !p-3 text-left transition-all hover:border-qubic-teal/50 hover:shadow-lg hover:shadow-qubic-teal/10 group"
                @click="selectPortfolioOwner(group.owner)">
          <!-- Header: owner + wallet count badge -->
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="flex items-center gap-1.5 min-w-0 flex-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-qubic-teal flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
              </svg>
              <span class="font-medium text-sm truncate group-hover:text-qubic-teal transition-colors">
                {{ store.hideAddresses ? '••••••' : group.owner }}
              </span>
            </div>
            <span class="text-xs px-2 py-0.5 rounded-md bg-qubic-teal/10 text-qubic-teal border border-qubic-teal/20 font-mono shrink-0">
              {{ group.wallets.length }}w
            </span>
          </div>

          <!-- Balance (hero value) -->
          <div class="font-mono text-base leading-tight mb-1" :class="group.hasNullBalance ? 'text-gray-500 italic' : 'text-gray-200'">
            {{ store.hideAddresses ? '••••••' : group.totalBalance.toLocaleString(store.locale) }}
            <span class="text-sm text-gray-500">QU</span>
          </div>

          <!-- Fiat value -->
          <div v-if="group.hasValue" class="font-mono text-sm text-gray-400 mb-0.5">
            {{ fmtFiat(group.totalValue) }}
          </div>

          <!-- P&L row -->
          <div v-if="group.hasCost" class="flex items-baseline gap-2 mt-1 flex-wrap">
            <span class="font-mono text-sm font-semibold"
                  :class="(group.totalValue - group.totalCost) >= 0 ? 'text-green-400' : 'text-red-400'">
              {{ (group.totalValue - group.totalCost) >= 0 ? '▲' : '▼' }}
              {{ fmtPct((group.totalValue - group.totalCost) / group.totalCost * 100) }}
            </span>
            <span class="font-mono text-xs"
                  :class="(group.totalValue - group.totalCost) >= 0 ? 'text-green-400/80' : 'text-red-400/80'">
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
        <!-- Back nav + owner summary -->
        <div class="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <button class="btn-ghost text-sm flex items-center gap-1.5" @click="backToOwners">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            {{ t('wallet.back_to_owners') }}
          </button>
          <div class="flex items-center gap-4 flex-wrap">
            <div>
              <div class="text-xs text-gray-500">{{ t('filter.owner') }}</div>
              <div class="font-medium">{{ store.hideAddresses ? '••••••' : selectedGroup.owner }}</div>
            </div>
            <div class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.balance') }}</div>
              <div class="font-mono text-sm">
                {{ store.hideAddresses ? '••••••' : selectedGroup.totalBalance.toLocaleString(store.locale) }} QU
              </div>
            </div>
            <div v-if="selectedGroup.hasValue" class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.value') }}</div>
              <div class="font-mono text-sm">{{ fmtFiat(selectedGroup.totalValue) }}</div>
            </div>
            <div v-if="selectedGroup.hasCost" class="text-right">
              <div class="text-xs text-gray-500">{{ t('wallet.pnl') }}</div>
              <div class="font-mono text-sm" :class="(selectedGroup.totalValue - selectedGroup.totalCost) >= 0 ? 'text-green-400' : 'text-red-400'">
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
                <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors">{{ maskLabel(w.label, w.id) }}</div>
                <div class="text-xs font-mono text-gray-500 truncate">{{ store.hideAddresses ? '••••••••••••' : w.id }}</div>
                <div class="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span class="text-xs font-mono" :class="w.balance == null ? 'text-gray-600 italic' : 'text-gray-400'">{{ fmtBalance(w) }} QU</span>
                  <span v-if="walletValue(w) != null" class="text-xs font-mono text-gray-400">· {{ fmtFiat(walletValue(w)) }}</span>
                  <span v-if="walletPnl(w) != null" class="text-xs font-mono"
                        :class="walletPnl(w) >= 0 ? 'text-green-400' : 'text-red-400'">
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
                <th class="th-right whitespace-nowrap">{{ t('wallet.balance') }} QU</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.value') }}</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.pnl') }}</th>
                <th class="th-right hidden lg:table-cell">{{ t('wallet.entries') }}</th>
                <th class="th-right"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in selectedGroup.wallets" :key="w.id" class="tr-row cursor-pointer hover:bg-white/[0.03] transition-colors group" @click="goToWallet(w.id)">
                <td class="td">
                  <div class="flex items-center gap-1.5 font-medium group-hover:text-qubic-teal transition-colors">
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
                    <span class="font-mono text-xs whitespace-nowrap" :class="w.balance == null ? 'text-gray-500 italic' : 'text-gray-300'">{{ fmtBalance(w) }}</span>
                    <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
                  </div>
                </td>
                <td class="td text-right hidden lg:table-cell font-mono text-xs whitespace-nowrap">
                  <span v-if="walletValue(w) != null" class="text-gray-300">{{ fmtFiat(walletValue(w)) }}</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="td text-right hidden lg:table-cell font-mono text-xs whitespace-nowrap">
                  <template v-if="walletPnl(w) != null">
                    <div :class="walletPnl(w) >= 0 ? 'text-green-400' : 'text-red-400'">
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
                  <router-link :to="`/wallets/${w.id}`" class="btn-action text-xs" @click.stop>{{ t('walletDetail.entries') }}</router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- =================== KONFIGURATION TAB =================== -->
    <template v-else>

    <!-- Add button + owner filter pills -->
    <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
      <div v-if="uniqueOwners.length" class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-gray-500 uppercase tracking-wide">{{ t('filter.owner') }}:</span>
        <button v-for="owner in uniqueOwners" :key="owner"
                :class="['btn-ghost text-xs py-1 px-3 transition-colors', selectedOwner === owner
                  ? 'bg-violet-500/20 border-violet-400 text-violet-300'
                  : 'text-gray-400 hover:bg-violet-500/10 hover:border-violet-400/60 hover:text-violet-300']"
                @click="selectedOwner = selectedOwner === owner ? null : owner">
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
            <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors">{{ maskLabel(w.label, w.id) }}</div>
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
          <button @click="startEdit(w)" class="btn-action text-xs">{{ t('wallet.edit') }}</button>
          <button @click="remove(w.id)" class="btn-delete text-xs">{{ t('wallet.delete') }}</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Desktop: table -->
  <div class="card overflow-hidden hidden sm:block">
    <table class="table-std">
      <thead class="thead-std">
        <tr>
          <th class="th">{{ t('wallet.label') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.owner') }}</th>
          <th class="th">{{ t('wallet.address') }}</th>
          <th class="th">{{ t('wallet.type') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.function') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.note') }}</th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap">{{ t('wallet.balance') }} QUBIC</th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap">{{ t('wallet.entries') }}</th>
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
                {{ maskLabel(w.label, w.id) }}
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>
            </td>
            <td class="td text-gray-400 hidden md:table-cell">{{ store.hideAddresses ? '••••••' : (w.owner || '—') }}</td>
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
                <button @click.stop="startEdit(w)" class="btn-action">{{ t('wallet.edit') }}</button>
                <button @click.stop="remove(w.id)" class="btn-delete">{{ t('wallet.delete') }}</button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
    </template><!-- end config tab -->
  </template>
</template>
