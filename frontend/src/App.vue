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

const store = useAppStore()
const { isSuppressed, suppressedUntil } = useDonationState()
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
  <div class="min-h-screen flex flex-col">
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
        {{ t('donation.banner_suppressed') }}
        {{ suppressedUntil === '2099-12-31' ? t('donation.check_forever') : suppressedUntil }}
      </span>
    </router-link>

    <AppNav />
    <DonationBanner />
    <main class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6">
      <router-view />
    </main>
    <MoneyAnimation />
    <AppFooter />
  </div>
</template>
