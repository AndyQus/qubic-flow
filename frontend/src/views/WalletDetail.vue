<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import EventsTable from '../components/EventsTable.vue'

const props = defineProps({ id: String })
const store = useAppStore()
const events = ref([])

const wallet = computed(() => store.wallets.find(w => w.id === props.id))

onMounted(async () => {
  events.value = await api.events.list({ wallet_id: props.id, limit: 200 })
})
</script>

<template>
  <div v-if="wallet" class="card mb-4">
    <div class="text-lg font-bold">{{ wallet.label }}</div>
    <div class="text-xs font-mono text-gray-400 break-all">{{ wallet.id }}</div>
    <div class="mt-2">
      <span class="pill">{{ wallet.wallet_type }}</span>
    </div>
  </div>
  <EventsTable :events="events" />
</template>
