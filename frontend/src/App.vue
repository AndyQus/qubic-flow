<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/app'
import { useWebSocket } from './composables/useWebSocket'
import { api } from './api'
import AppHeader from './components/AppHeader.vue'
import AppNav from './components/AppNav.vue'

const store = useAppStore()
useWebSocket()

onMounted(async () => {
  store.setTheme(store.theme)
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
    <main class="flex-1 container mx-auto px-4 py-6 max-w-7xl">
      <router-view />
    </main>
  </div>
</template>
