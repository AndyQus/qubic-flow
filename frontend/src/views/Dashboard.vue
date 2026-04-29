<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'
import WalletFilter from '../components/WalletFilter.vue'
import PageHeader from '../components/PageHeader.vue'
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
const intervalId = setInterval(loadStats, 60_000)
onUnmounted(() => clearInterval(intervalId))
</script>

<template>
  <div class="space-y-3">
    <PageHeader :title="t('nav.dashboard')" :hint="t('page_hint.dashboard')" />
    <WalletFilter v-model="selectedWallets" />
    <StatsPanel :stats="stats" :loading="loadingStats" />
    <EventsTable :events="store.events" :loading="loadingEvents" :title="t('event.last10')" :readonly="true" />
  </div>
</template>
