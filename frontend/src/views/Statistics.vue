<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement,
  CategoryScale, LinearScale, PointElement, Filler,
} from 'chart.js'

ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, Filler)

const snaps = ref([])

onMounted(async () => { snaps.value = await api.stats.snapshots() })

const chartData = computed(() => {
  const items = [...snaps.value].reverse()
  return {
    labels: items.map(s => `W${s.week}/${s.year}`),
    datasets: [
      {
        label: 'Events',
        data: items.map(s => s.event_count),
        borderColor: '#2dd4bf',
        backgroundColor: 'rgba(45, 212, 191, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#e5e7eb' } } },
  scales: {
    x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
    y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
  },
}
</script>

<template>
  <h2 class="text-xl font-bold mb-4">Statistiken</h2>
  <div class="card" style="height: 400px">
    <Line v-if="snaps.length" :data="chartData" :options="chartOptions" />
    <div v-else class="text-center text-gray-500 pt-16">Noch keine Snapshots vorhanden</div>
  </div>
</template>
