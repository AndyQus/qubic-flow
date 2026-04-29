<script setup>
import { computed, onMounted } from 'vue'
import { useAppStore } from './stores/app'
import { useWebSocket } from './composables/useWebSocket'
import { useDonationState } from './composables/useDonationState'
import { useTranslation } from 'i18next-vue'
import { api } from './api'
import AppHeader from './components/AppHeader.vue'
import AppNav from './components/AppNav.vue'
import MoneyAnimation from './components/MoneyAnimation.vue'
import DonationBanner from './components/DonationBanner.vue'
import AppFooter from './components/AppFooter.vue'
import { copyToast } from './composables/useQubicUtils'

const store = useAppStore()
const { isSuppressed, suppressedUntil, donorRank } = useDonationState()
const { t } = useTranslation()
const isLight = computed(() => store.theme === 'light')
useWebSocket()

onMounted(async () => {
  store.setTheme(store.theme)
  document.documentElement.style.fontSize = store.fontSize + '%'
  try {
    const [wallets, nodes] = await Promise.all([api.wallets.list(), api.nodes.list()])
    store.wallets = wallets
    store.nodes = nodes
  } catch (e) {
    console.error('Initial load failed', e)
  }
})
</script>

<template>
  <div class="min-h-screen flex flex-col overflow-x-hidden">
    <AppHeader />

    <!-- Dankeschön-Leiste Mobile (nur < sm) -->
    <router-link v-if="isSuppressed" to="/support"
      class="sm:hidden flex items-center justify-center gap-1.5 px-4 py-1.5 text-[11px] font-semibold border-b transition-colors"
      :class="isLight
        ? 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100'
        : 'bg-[#9acd32]/10 border-[#9acd32]/30 text-[#9acd32] hover:bg-[#9acd32]/20'">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
        <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
      </svg>
      <span>
        {{ donorRank
        ? (suppressedUntil === '2099-12-31'
            ? t('donation.banner_suppressed_rank_forever', { rank: donorRank.name })
            : t('donation.banner_suppressed_rank', { rank: donorRank.name, date: suppressedUntil }))
        : (suppressedUntil === '2099-12-31'
            ? t('donation.banner_suppressed_forever')
            : t('donation.banner_suppressed') + ' ' + suppressedUntil) }}
      </span>
    </router-link>

    <AppNav />
    <DonationBanner />
    <main class="flex-1 w-full min-w-0 px-4 sm:px-6 lg:px-8 py-6">
      <router-view />
    </main>
    <MoneyAnimation />
    <AppFooter />

    <!-- Copy-Toast -->
    <Transition name="copy-toast">
      <div v-if="copyToast"
           class="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg border border-qubic-border/60 bg-qubic-surface px-4 py-2.5 font-mono text-xs text-qubic-teal shadow-xl pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        {{ copyToast }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.copy-toast-enter-active,
.copy-toast-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.copy-toast-enter-from,
.copy-toast-leave-to    { opacity: 0; transform: translateY(6px); }
</style>
