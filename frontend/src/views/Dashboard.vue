<script setup>
import { onMounted, ref, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'
import WalletFilter from '../components/WalletFilter.vue'
import PageLoader from '../components/PageLoader.vue'

const store = useAppStore()
const selectedWallets = ref([])
const loading = ref(true)

async function loadEvents() {
  loading.value = true
  try {
    const params = { limit: 10 }
    if (selectedWallets.value.length) params.wallet_ids = selectedWallets.value
    store.events = await api.events.list(params)
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

watch(selectedWallets, loadEvents, { deep: true })
onMounted(loadEvents)
</script>

<template>
  <div class="space-y-3">
    <WalletFilter v-model="selectedWallets" />
    <PageLoader v-if="loading" />
    <template v-else>
      <StatsPanel />
      <EventsTable :events="store.events" />
    </template>
  </div>
</template>
