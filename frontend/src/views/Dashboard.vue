<script setup>
import { onMounted, ref, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'
import WalletFilter from '../components/WalletFilter.vue'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()
const selectedWallets = ref([])
const loadingEvents = ref(true)
const loadingStats  = ref(true)
const stats         = ref(null)

async function loadStats() {
  loadingStats.value = true
  try { stats.value = await api.stats.current(selectedWallets.value) } catch (e) { console.error(e) }
  finally { loadingStats.value = false }
}

async function loadEvents() {
  loadingEvents.value = true
  try {
    const params = { limit: 10 }
    if (selectedWallets.value.length) params.wallet_ids = selectedWallets.value
    store.events = await api.events.list(params)
  } catch (e) { console.error(e) }
  finally { loadingEvents.value = false }
}

watch(selectedWallets, () => { loadStats(); loadEvents() }, { deep: true })
onMounted(() => { loadStats(); loadEvents() })
setInterval(loadStats, 60_000)
</script>

<template>
  <div class="space-y-3">
    <WalletFilter v-model="selectedWallets" />
    <StatsPanel :stats="stats" :loading="loadingStats" />
    <EventsTable :events="store.events" :loading="loadingEvents" :title="t('event.last10')" />
  </div>
</template>
