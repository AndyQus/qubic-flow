<script setup>
import { useTranslation } from 'i18next-vue'

const { t } = useTranslation()

const otherApps = [
  { name: 'MyLedger',  url: 'https://myledger.qubic.tools',    desc: 'Qubic Ledger Tool' },
  { name: 'Dividends', url: 'https://dividends.qubic.tools',   desc: 'Dividend Tracker' },
  { name: 'Auctions',  url: 'https://auctions.qubic.tools',    desc: 'Qubic Auction Monitor' },
  { name: 'Doge-Mining-Stats', url: 'https://doge.qubic.tools', desc: 'Doge Mining Stats' },
  { name: 'Explorer',  url: 'https://live.qubic.org/explorer', desc: 'Qubic Live Explorer' },
  { name: 'Live',      url: 'https://live.qubic.org',          desc: 'Qubic Live Network' },
  { name: 'VS Marketplace — QPI Language Support', url: 'https://marketplace.visualstudio.com/items?itemName=AndyQus.qubic-org-qpi', desc: 'VSCode Extension' },
]
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-8">

    <!-- Header (full width) -->
    <div class="text-center space-y-1">
      <h1 class="text-2xl font-bold text-qubic-teal">{{ t('donation.page_title') }}</h1>
      <p class="text-sm text-gray-400">{{ t('donation.page_subtitle') }}</p>
    </div>

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

        <!-- Honorary thank-you -->
        <div class="card !p-6">
          <p class="text-sm text-amber-400/80 italic text-center">{{ t('donation.honorary_eko') }}</p>
        </div>

    </div>

  </div>
</template>
