<script setup>
import { onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import StatsPanel from '../components/StatsPanel.vue'
import EventsTable from '../components/EventsTable.vue'

const store = useAppStore()

onMounted(async () => {
  try {
    const events = await api.events.list({ limit: 100 })
    store.events = events
  } catch (e) { console.error(e) }
})
</script>

<template>
  <StatsPanel />
  <EventsTable :events="store.events" />
</template>
