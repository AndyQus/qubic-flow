<script setup>
import { ref, onMounted } from 'vue'
import { useTranslation } from 'i18next-vue'
import QRCode from 'qrcode'
import { api } from '../api'

const { t } = useTranslation()

const DONATION_ADDRESS = 'CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI'

const qrDataUrl = ref('')
const copied = ref(false)
const donationStatus = ref(null)

const DISCORD_URL = 'https://discord.com/channels/768887649540243497/1455213108535627917'

const tiers = [
  { amount: '1.000.000 QU',  label: 'tier_1m' },
  { amount: '3.000.000 QU',  label: 'tier_3m' },
  { amount: '6.000.000 QU',  label: 'tier_6m' },
  { amount: '12.000.000 QU', label: 'tier_12m' },
]

// Supporters who donated > 100,000,000 QU and gave permission to be listed
// Format: { name, amount_qu, date }
const supporters = [
]

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
  await navigator.clipboard.writeText(DONATION_ADDRESS)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
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
})
</script>

<template>
  <div class="max-w-5xl mx-auto space-y-8">

    <!-- Header (full width) -->
    <div class="text-center space-y-1">
      <h1 class="text-2xl font-bold text-qubic-teal">{{ t('donation.page_title') }}</h1>
      <p class="text-sm text-gray-400">{{ t('donation.page_subtitle') }}</p>
    </div>

    <!-- Two-column grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

      <!-- LEFT column: About, Why, Tiers, Forever -->
      <div class="space-y-6">

        <!-- About AndyQus -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-3">
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
        </div>

        <!-- Why support -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-3">
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

        <!-- Tiers -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-4">
          <h2 class="font-semibold text-white text-base">{{ t('donation.tiers_title') }}</h2>
          <p class="text-xs text-gray-400">{{ t('donation.tiers_note') }}</p>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-gray-400 text-xs border-b border-qubic-border">
                  <th class="text-left pb-2 font-medium">Betrag / Amount</th>
                  <th class="text-left pb-2 font-medium">{{ t('donation.tiers_title').split(' ')[0] }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-qubic-border/40">
                <tr v-for="tier in tiers" :key="tier.label" class="text-gray-300">
                  <td class="py-2 font-mono text-qubic-teal">{{ tier.amount }}</td>
                  <td class="py-2">{{ t(`donation.${tier.label}`) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Forever tier via Discord -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-3">
          <h2 class="font-semibold text-white text-base">{{ t('donation.tier_forever') }}</h2>
          <p class="text-sm text-gray-300">{{ t('donation.forever_desc') }}</p>
          <a :href="DISCORD_URL" target="_blank" rel="noopener noreferrer"
             class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/>
            </svg>
            {{ t('donation.forever_cta') }}
          </a>
        </div>

      </div>

      <!-- RIGHT column: QR+Address, Payment detected, Supporters -->
      <div class="space-y-6">

        <!-- QR + Address -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-4">
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

        <!-- Payment detected (only shown when payment found) -->
        <div v-if="donationStatus && donationStatus.suppressed_until"
             class="bg-emerald-500/10 border border-emerald-500/40 rounded-xl p-6 space-y-3">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
            <h2 class="font-semibold text-emerald-400 text-base">{{ t('donation.check_title') }}</h2>
          </div>
          <div class="space-y-2">
            <div class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_total') }}</span>
              <span class="text-emerald-400 font-mono">{{ donationStatus.total_qu.toLocaleString() }} QU</span>
            </div>
            <div v-if="!donationStatus.forever" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_months') }}</span>
              <span class="text-white font-semibold">{{ donationStatus.months_earned }}</span>
            </div>
            <div v-if="donationStatus.last_payment_amount" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_last_amount') }}</span>
              <span class="text-emerald-400 font-mono">{{ donationStatus.last_payment_amount.toLocaleString() }} QU</span>
            </div>
            <div v-if="donationStatus.last_payment_date" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_last_date') }}</span>
              <span class="text-white">{{ donationStatus.last_payment_date }}</span>
            </div>
            <div v-if="donationStatus.suppressed_until" class="flex justify-between text-sm">
              <span class="text-gray-400">{{ t('donation.check_until') }}</span>
              <span class="text-emerald-400 font-semibold">
                {{ donationStatus.forever ? t('donation.check_forever') : donationStatus.suppressed_until }}
              </span>
            </div>
          </div>
        </div>

        <!-- Supporters -->
        <div class="bg-qubic-card border border-qubic-border rounded-xl p-6 space-y-4">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
              <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
            </svg>
            <h2 class="font-semibold text-white text-base">{{ t('donation.supporters_title') }}</h2>
          </div>
          <p class="text-sm text-gray-400 leading-relaxed">{{ t('donation.supporters_text') }}</p>

          <div v-if="supporters.length === 0" class="text-sm text-gray-500 italic text-center py-4">
            {{ t('donation.supporters_empty') }}
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-gray-400 text-xs border-b border-qubic-border">
                  <th class="text-left pb-2 font-medium">Name</th>
                  <th class="text-left pb-2 font-medium">{{ t('donation.supporters_amount') }}</th>
                  <th class="text-left pb-2 font-medium">{{ t('donation.supporters_date') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-qubic-border/40">
                <tr v-for="s in supporters" :key="s.name + s.date" class="text-gray-300">
                  <td class="py-2 font-medium text-white flex items-center gap-1.5">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
                    </svg>
                    {{ s.name }}
                  </td>
                  <td class="py-2 font-mono text-amber-400">{{ s.amount_qu.toLocaleString() }} QU</td>
                  <td class="py-2 text-gray-400">{{ s.date }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>
