<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useTranslation } from 'i18next-vue'
import QRCode from 'qrcode'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import { setDebugSuppression, setDebugTotalQu, DONATION_RANKS, getDonorRank } from '../composables/useDonationState'
import { useQubicUtils } from '../composables/useQubicUtils'

const { copyValue } = useQubicUtils()

const { t } = useTranslation()
const store = useAppStore()

const DONATION_ADDRESS = 'CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI'

const qrDataUrl = ref('')
const copied = ref(false)
const donationStatus = ref(null)
const topDonors = ref([])
const topDonorsLoading = ref(true)
const donationHistory = ref([])
const donationTotalQu = ref(0)

const isDebug = import.meta.env.DEV
const debugSimulate = ref(false)
const debugScenario = ref('spark')

const DEBUG_SCENARIOS = {
  spark: {
    label: '⚡ Quantum Spark · 1 Mio',
    status: { total_qu: 1_000_000, months_earned: 1, suppressed_until: '2026-05-26', forever: false,
              last_payment_amount: 1_000_000, last_payment_date: '2026-04-26' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 1_000_000, tick: 17500000, date: '2026-04-26' },
    ],
    totalQu: 1_000_000,
  },
  knight: {
    label: '🗡️ Qubic Knight · 10 Mio',
    status: { total_qu: 10_000_000, months_earned: 10, suppressed_until: '2027-02-26', forever: false,
              last_payment_amount: 10_000_000, last_payment_date: '2026-04-26' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 10_000_000, tick: 17500000, date: '2026-04-26' },
    ],
    totalQu: 10_000_000,
  },
  avenger: {
    label: '⚔️ Crypto Avenger · 50 Mio',
    status: { total_qu: 50_000_000, months_earned: 50, suppressed_until: '2030-06-26', forever: false,
              last_payment_amount: 50_000_000, last_payment_date: '2026-04-26' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 50_000_000, tick: 17500000, date: '2026-04-26' },
    ],
    totalQu: 50_000_000,
  },
  guardian: {
    label: '🛡️ Block Guardian · 100 Mio',
    status: { total_qu: 100_000_000, months_earned: 100, suppressed_until: '2099-12-31', forever: true,
              last_payment_amount: 100_000_000, last_payment_date: '2026-04-26' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 100_000_000, tick: 17500000, date: '2026-04-26' },
    ],
    totalQu: 100_000_000,
  },
  diamond: {
    label: '💎 Diamond Node · 500 Mio',
    status: { total_qu: 500_000_000, months_earned: 500, suppressed_until: '2099-12-31', forever: true,
              last_payment_amount: 500_000_000, last_payment_date: '2026-04-01' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 500_000_000, tick: 17450000, date: '2026-04-01' },
    ],
    totalQu: 500_000_000,
  },
  legend: {
    label: '👑 Chain Legend · 1 Mrd',
    status: { total_qu: 1_000_000_000, months_earned: 1000, suppressed_until: '2099-12-31', forever: true,
              last_payment_amount: 500_000_000, last_payment_date: '2026-04-01' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 500_000_000, tick: 17450000, date: '2026-04-01' },
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 500_000_000, tick: 14500000, date: '2025-12-20' },
    ],
    totalQu: 1_000_000_000,
  },
  multi: {
    label: '3 Zahlungen · 4 Mio · aktiv bis Jun 10',
    status: { total_qu: 4_000_000, months_earned: 4, suppressed_until: '2026-06-10', forever: false,
              last_payment_amount: 2_000_000, last_payment_date: '2026-04-10' },
    history: [
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 2_000_000, tick: 17480000, date: '2026-04-10' },
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 1_000_000, tick: 17000000, date: '2026-03-01' },
      { address: 'ANDYQUSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', amount: 1_000_000, tick: 16500000, date: '2026-01-15' },
    ],
    totalQu: 4_000_000,
  },
}

const effectiveDonationStatus = computed(() =>
  isDebug && debugSimulate.value ? DEBUG_SCENARIOS[debugScenario.value].status : donationStatus.value
)

if (isDebug) {
  watch([debugSimulate, debugScenario], () => {
    const s = debugSimulate.value ? DEBUG_SCENARIOS[debugScenario.value] : null
    setDebugSuppression(s?.status.suppressed_until ?? null)
    setDebugTotalQu(s?.totalQu ?? null)
  })
  onUnmounted(() => {
    setDebugSuppression(null)
    setDebugTotalQu(null)
  })
}
const effectiveDonationHistory = computed(() =>
  isDebug && debugSimulate.value ? DEBUG_SCENARIOS[debugScenario.value].history : donationHistory.value
)
const effectiveDonationTotalQu = computed(() =>
  isDebug && debugSimulate.value ? DEBUG_SCENARIOS[debugScenario.value].totalQu : donationTotalQu.value
)

const rankDesc = (rank) => store.lang === 'de' ? rank.descDe : rank.descEn
const currentDonorRank = computed(() => getDonorRank(effectiveDonationTotalQu.value))

const otherApps = [
  { name: 'MyLedger',  url: 'https://myledger.qubic.tools',    desc: 'Qubic Ledger Tool' },
  { name: 'Dividends', url: 'https://dividends.qubic.tools',   desc: 'Dividend Tracker' },
  { name: 'Auctions',  url: 'https://auctions.qubic.tools',    desc: 'Qubic Auction Monitor' },
  { name: 'Doge-Mining-Stats', url: 'https://doge.qubic.tools', desc: 'Doge Mining Stats' },
  { name: 'Explorer',  url: 'https://live.qubic.org/explorer', desc: 'Qubic Live Explorer' },
  { name: 'Live',      url: 'https://live.qubic.org',          desc: 'Qubic Live Network' },
  { name: 'VS Marketplace — QPI Language Support', url: 'https://marketplace.visualstudio.com/items?itemName=AndyQus.qubic-org-qpi', desc: 'VSCode Extension' },
]

async function copyAddress() {
  try {
    await navigator.clipboard.writeText(DONATION_ADDRESS)
  } catch {
    const el = document.createElement('textarea')
    el.value = DONATION_ADDRESS
    el.style.position = 'fixed'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function explorerUrl(address) {
  return `https://explorer.qubic.org/network/address/${address}`
}

function shortAddr(address) {
  return address.slice(0, 8) + '…' + address.slice(-8)
}

onMounted(async () => {
  qrDataUrl.value = await QRCode.toDataURL(DONATION_ADDRESS, {
    width: 220,
    margin: 2,
    color: { dark: '#000000', light: '#ffffff' },
  })
  try {
    donationStatus.value = await api.events.donationCheck()
  } catch {}
  try {
    const res = await api.events.donationTop()
    topDonors.value = res.donors || []
  } catch {
  } finally {
    topDonorsLoading.value = false
  }
  try {
    const res = await api.events.donationHistory(true)
    donationHistory.value = res.transactions || []
    donationTotalQu.value = res.total_qu || 0
  } catch {}
})
</script>

<template>
  <div class="max-w-screen-2xl mx-auto space-y-8">

    <!-- Header (full width) -->
    <div class="text-center space-y-1">
      <h1 class="text-2xl font-bold text-qubic-teal">{{ t('donation.page_title') }}</h1>
      <p class="text-sm text-gray-400">{{ t('donation.page_subtitle') }}</p>
    </div>

    <!-- Debug simulator (dev mode only) -->
    <div v-if="isDebug" class="border border-dashed border-yellow-500/60 rounded-xl p-4 bg-yellow-500/5 space-y-3">
      <div class="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        </svg>
        <span class="text-xs font-semibold text-yellow-400 uppercase tracking-wide">Debug — nur im Dev-Modus sichtbar</span>
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <label class="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" v-model="debugSimulate" class="accent-yellow-400" />
          <span class="text-sm text-yellow-300">Zahlung simulieren</span>
        </label>
        <div v-if="debugSimulate" class="flex flex-wrap gap-2">
          <button
            v-for="(s, key) in DEBUG_SCENARIOS" :key="key"
            @click="debugScenario = key"
            class="px-3 py-1 rounded text-xs font-medium transition-colors"
            :class="debugScenario === key ? 'bg-yellow-400 text-black' : 'bg-yellow-400/20 text-yellow-300 hover:bg-yellow-400/40'"
          >
            {{ s.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Three-column grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

      <!-- COL 1: About, Why -->
      <div class="space-y-6">

        <!-- About AndyQus -->
        <div class="card !p-6 space-y-3">
          <h2 class="font-semibold text-white text-base">{{ t('donation.about_title') }}</h2>
          <p class="text-sm text-gray-300 leading-relaxed">
            {{ t('donation.about_core_prefix') }}
            <a href="https://explorer.qubic.org" target="_blank" rel="noopener noreferrer" class="text-qubic-teal hover:text-white transition-colors">Qubic Explorer</a>{{ t('donation.about_core_mid1') }}
            Quottery
            {{ t('donation.about_core_mid2') }}
            <a href="https://wallet.qubic.org" target="_blank" rel="noopener noreferrer" class="text-qubic-teal hover:text-white transition-colors">Qubic Web Wallet</a>
            {{ t('donation.about_core_suffix') }}
          </p>
          <p class="text-sm text-gray-300 leading-relaxed">
            {{ t('donation.about_tools_prefix') }}
            <template v-for="(app, i) in otherApps" :key="app.url">
              <a :href="app.url" target="_blank" rel="noopener noreferrer" class="text-qubic-teal hover:text-white transition-colors">{{ app.name }}</a><span v-if="i < otherApps.length - 1">, </span>
            </template>,
            {{ t('donation.about_text2') }}
          </p>
          <!-- Open Source -->
          <div class="border-t border-qubic-border pt-3 space-y-2">
            <p class="text-sm text-gray-300 leading-relaxed">{{ t('donation.about_open_source') }}</p>
            <a href="https://github.com/AndyQus/qubic-flow" target="_blank" rel="noopener noreferrer"
               class="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-qubic-border bg-qubic-bg hover:bg-qubic-card text-sm text-gray-300 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              {{ t('donation.about_github_btn') }}
            </a>
          </div>
        </div>

        <!-- Why support -->
        <div class="card !p-6 space-y-3">
          <h2 class="font-semibold text-white text-base">{{ t('donation.why_title') }}</h2>
          <ul class="space-y-2">
            <li v-for="key in ['why_dev','why_new_projects','why_support','why_time','why_appreciation']" :key="key"
                class="flex items-start gap-2 text-sm text-gray-300">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-qubic-teal flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
              </svg>
              {{ t(`donation.${key}`) }}
            </li>
          </ul>
        </div>

      </div>

      <!-- COL 2: Payment detected, QR+Address, Tiers -->
      <div class="space-y-6">

        <!-- Payment detected (only shown when payment found) -->
        <div v-if="effectiveDonationStatus && effectiveDonationStatus.suppressed_until"
             class="bg-emerald-500/10 border border-emerald-500/40 rounded-xl p-6 space-y-3">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
            <h2 class="font-semibold text-emerald-400 text-base">
              {{ currentDonorRank ? t('donation.check_title_rank', { rank: currentDonorRank.name }) : t('donation.check_title') }}
            </h2>
          </div>
          <div class="space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_total') }}</span>
              <span class="text-emerald-400 font-mono cursor-copy select-none" @dblclick.prevent="copyValue(effectiveDonationStatus.total_qu)">{{ effectiveDonationStatus.total_qu.toLocaleString() }} QU</span>
            </div>
            <div v-if="!effectiveDonationStatus.forever" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_months') }}</span>
              <span class="text-white font-semibold">{{ effectiveDonationStatus.months_earned }}</span>
            </div>
            <div v-if="effectiveDonationStatus.last_payment_amount" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_last_amount') }}</span>
              <span class="text-emerald-400 font-mono cursor-copy select-none" @dblclick.prevent="copyValue(effectiveDonationStatus.last_payment_amount)">{{ effectiveDonationStatus.last_payment_amount.toLocaleString() }} QU</span>
            </div>
            <div v-if="effectiveDonationStatus.last_payment_date" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_last_date') }}</span>
              <span class="text-white">{{ effectiveDonationStatus.last_payment_date }}</span>
            </div>
            <div v-if="effectiveDonationStatus.suppressed_until" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_until') }}</span>
              <span class="text-emerald-400 font-semibold">
                {{ effectiveDonationStatus.forever ? t('donation.check_forever') : effectiveDonationStatus.suppressed_until }}
              </span>
            </div>
          </div>
        </div>

        <!-- QR + Address -->
        <div class="card !p-6 space-y-4">
          <h2 class="font-semibold text-white text-base">{{ t('donation.address_label') }}</h2>
          <div class="flex flex-col items-center gap-4">
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="Donation QR Code" class="rounded-lg w-[200px] h-[200px]" />
            <div v-else class="w-[200px] h-[200px] bg-qubic-border rounded-lg animate-pulse" />
            <div class="w-full space-y-3">
              <p class="font-mono text-xs text-gray-200 break-all leading-relaxed bg-qubic-bg rounded-lg p-3 border border-qubic-border">
                {{ DONATION_ADDRESS }}
              </p>
              <button
                @click="copyAddress"
                class="w-full px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                :class="copied ? 'bg-emerald-600 text-white' : 'bg-qubic-teal text-qubic-bg hover:bg-qubic-teal/90'"
              >
                {{ copied ? t('donation.copied') : t('donation.copy_address') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Supporter Ranks -->
        <div class="card !p-6 space-y-3">
          <h2 class="font-semibold text-white text-base">{{ t('donation.tiers_title') }}</h2>
          <p class="text-sm text-gray-300 leading-relaxed">{{ t('donation.tiers_note') }}</p>
          <div class="divide-y divide-qubic-border/30">
            <div v-for="rank in DONATION_RANKS" :key="rank.name"
                 class="flex items-center gap-3 py-2.5">
              <span class="text-2xl flex-shrink-0">{{ rank.icon }}</span>
              <div class="flex-1 min-w-0">
                <div class="font-semibold text-sm" :style="{ color: rank.color }">{{ rank.name }}</div>
                <div class="text-xs text-gray-500">{{ rankDesc(rank) }}</div>
              </div>
              <div class="font-mono text-xs text-right flex-shrink-0" :style="{ color: rank.color }">
                ≥ {{ rank.minQu.toLocaleString() }} QU
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- COL 3: Top Supporters + Donation History -->
      <div class="space-y-6">

        <!-- Top 20 Supporters -->
        <div class="card !p-6 space-y-4">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
            </svg>
            <h2 class="font-semibold text-white text-base">{{ t('donation.supporters_title') }}</h2>
          </div>
          <p class="text-xs text-gray-400">{{ t('donation.supporters_text') }}</p>

          <div v-if="topDonorsLoading" class="flex justify-center py-6">
            <svg class="w-6 h-6 text-amber-400 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
          </div>
          <div v-else-if="topDonors.length === 0" class="text-sm text-gray-500 italic text-center py-4">
            {{ t('donation.supporters_empty') }}
          </div>
          <div v-else-if="topDonors.length > 0">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-gray-400 border-b border-qubic-border">
                  <th class="text-left pb-2 font-medium">#</th>
                  <th class="text-left pb-2 font-medium">Rang</th>
                  <th class="text-left pb-2 font-medium">{{ t('donation.history_sender') }}</th>
                  <th class="text-right pb-2 font-medium">{{ t('donation.supporters_amount') }}</th>
                  <th class="text-right pb-2 font-medium">{{ t('donation.supporters_date') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-qubic-border/40">
                <tr v-for="(donor, i) in topDonors" :key="donor.address" class="text-gray-300">
                  <td class="py-1.5 text-gray-500">{{ i + 1 }}</td>
                  <td class="py-1.5 whitespace-nowrap">
                    <template v-if="getDonorRank(donor.total_qu)">
                      <span class="mr-1">{{ getDonorRank(donor.total_qu).icon }}</span>
                      <span class="font-semibold text-xs" :style="{ color: getDonorRank(donor.total_qu).color }">
                        {{ getDonorRank(donor.total_qu).name }}
                      </span>
                    </template>
                    <span v-else class="text-gray-600">—</span>
                  </td>
                  <td class="py-1.5">
                    <span class="font-mono text-gray-300" :title="donor.address">
                      {{ donor.address.slice(0, 5) }}
                    </span>
                  </td>
                  <td class="py-1.5 text-right font-mono text-amber-400 cursor-copy select-none" @dblclick.prevent="copyValue(donor.total_qu)">{{ donor.total_qu.toLocaleString() }}</td>
                  <td class="py-1.5 text-right text-gray-400">{{ donor.date }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- Honorary thank-you -->
          <p class="text-xs text-amber-400/80 italic pt-1 text-center">{{ t('donation.honorary_eko') }}</p>
        </div>

        <!-- Donation History (only shown when payment detected) -->
        <div v-if="effectiveDonationStatus && effectiveDonationStatus.suppressed_until"
             class="bg-emerald-500/10 border border-emerald-500/40 rounded-xl p-6 space-y-4">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
            </svg>
            <h2 class="font-semibold text-emerald-400 text-base">{{ t('donation.history_title') }}</h2>
          </div>
          <!-- Total -->
          <div class="flex justify-between items-center bg-emerald-500/10 rounded-lg px-4 py-2 border border-emerald-500/30">
            <span class="text-sm text-gray-400">{{ t('donation.history_total') }}</span>
            <span class="font-mono text-emerald-400 font-semibold cursor-copy select-none" @dblclick.prevent="copyValue(effectiveDonationTotalQu)">{{ effectiveDonationTotalQu.toLocaleString() }} QU</span>
          </div>

          <div v-if="effectiveDonationHistory.length === 0" class="text-sm text-gray-500 italic text-center py-4">
            {{ t('donation.history_empty') }}
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-gray-400 border-b border-emerald-500/30">
                  <th class="text-left pb-2 font-medium">{{ t('donation.history_sender') }}</th>
                  <th class="text-right pb-2 font-medium">{{ t('donation.history_amount') }}</th>
                  <th class="text-right pb-2 font-medium">{{ t('donation.history_date') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-emerald-500/20">
                <tr v-for="tx in effectiveDonationHistory" :key="tx.tick + tx.address" class="text-gray-300">
                  <td class="py-1.5">
                    <a :href="explorerUrl(tx.address)" target="_blank" rel="noopener noreferrer"
                       class="font-mono text-emerald-400 hover:text-white transition-colors"
                       :title="tx.address">
                      {{ shortAddr(tx.address) }}
                    </a>
                  </td>
                  <td class="py-1.5 text-right font-mono text-emerald-400 cursor-copy select-none" @dblclick.prevent="copyValue(tx.amount)">{{ tx.amount.toLocaleString() }}</td>
                  <td class="py-1.5 text-right text-gray-400">{{ tx.date }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>
