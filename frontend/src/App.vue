<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/app'
import { useWebSocket } from './composables/useWebSocket'
import { api } from './api'
import AppHeader from './components/AppHeader.vue'
import AppNav from './components/AppNav.vue'
import MoneyAnimation from './components/MoneyAnimation.vue'
import DonationBanner from './components/DonationBanner.vue'

const store = useAppStore()
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
    <AppNav />
    <DonationBanner />
    <main class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6">
      <router-view />
    </main>
    <MoneyAnimation />
  </div>
</template>
