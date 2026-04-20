<script setup>
import { onMounted, ref, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'
import WalletFilter from '../components/WalletFilter.vue'

const store = useAppStore()
const selectedWallets = ref([])

async function loadEvents() {
  try {
    const params = { limit: 10 }
    if (selectedWallets.value.length) params.wallet_ids = selectedWallets.value
    store.events = await api.events.list(params)
  } catch (e) { console.error(e) }
}

watch(selectedWallets, loadEvents, { deep: true })
onMounted(loadEvents)
</script>

<template>
  <div class="space-y-6">
    <StatsPanel />
    <WalletFilter v-model="selectedWallets" />
    <EventsTable :events="store.events" />
  </div>
</template>
