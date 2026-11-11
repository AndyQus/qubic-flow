<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from './stores/app'
import { useWebSocket } from './composables/useWebSocket'
import { api } from './api'
import AppHeader from './components/AppHeader.vue'
import AppNav from './components/AppNav.vue'
import MoneyAnimation from './components/MoneyAnimation.vue'
import AppFooter from './components/AppFooter.vue'
import { copyToast } from './composables/useQubicUtils'

const store = useAppStore()
useWebSocket()

async function checkLogErrors() {
  try {
    const res = await api.nodes.logErrorCheck()
    store.setNodeLogError(res.has_error)
  } catch { /* ignore */ }
}

let _logErrorInterval = null

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
  await checkLogErrors()
  _logErrorInterval = setInterval(checkLogErrors, 60_000)
})

onUnmounted(() => clearInterval(_logErrorInterval))
</script>

<template>
  <div class="min-h-screen flex flex-col overflow-x-hidden">
    <AppHeader />
    <AppNav />
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
        <span class="not-italic">{{ copyToast }}</span>
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
