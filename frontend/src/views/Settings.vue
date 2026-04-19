<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import i18next from 'i18next'
import { exportUrl } from '../api'
import { ref, computed } from 'vue'

const store = useAppStore()
const { t } = useTranslation()
const year = ref(new Date().getFullYear())

function setLang(l) {
  store.setLang(l)
  i18next.changeLanguage(l)
}

const previewRows = ref([
  { id: 'p1', time: '18:42:01', direction: 'IN',  amount: '5.000', isNew: false },
  { id: 'p2', time: '18:40:55', direction: 'OUT', amount: '1.200', isNew: false },
  { id: 'p3', time: '18:39:10', direction: 'IN',  amount: '320',   isNew: false },
])

const previewAnimClass = computed(() => {
  if (store.animation === 'push-down') return 'anim-push-down'
  if (store.animation === 'slide-in') return 'anim-slide-in'
  return 'anim-beam-drop'
})

function simulate() {
  const dir = Math.random() > 0.5 ? 'IN' : 'OUT'
  const amount = (Math.floor(Math.random() * 9000) + 500).toLocaleString('de-DE')
  const now = new Date().toLocaleTimeString('de-DE')
  const newRow = { id: `p${Date.now()}`, time: now, direction: dir, amount, isNew: true }
  previewRows.value.unshift(newRow)
  if (previewRows.value.length > 5) previewRows.value.pop()
  setTimeout(() => {
    const row = previewRows.value.find(r => r.id === newRow.id)
    if (row) row.isNew = false
  }, 60_000)
}
</script>

<template>
  <div class="space-y-6">
    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('settings.animation') }}</h3>
      <div class="flex flex-wrap gap-2 mb-4">
        <button v-for="a in ['push-down', 'slide-in', 'beam-drop']" :key="a"
                :class="['btn-ghost', store.animation === a && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="store.setAnimation(a)">
          {{ t(`settings.${a.replace('-', '_')}`) }}
        </button>
        <button class="btn ml-auto" @click="simulate">▶ {{ t('settings.preview') }}</button>
      </div>

      <!-- Live-Vorschau (div-basiert, damit alle CSS-Animationen greifen) -->
      <div class="rounded-lg border border-qubic-border overflow-hidden bg-qubic-bg/50 text-xs">
        <div class="flex border-b border-qubic-border text-gray-500 uppercase px-3 py-1.5">
          <span class="w-20">Zeit</span>
          <span class="w-16">Richtung</span>
          <span class="font-mono">Betrag</span>
        </div>
        <div v-for="row in previewRows" :key="row.id"
             :class="[
               row.isNew ? previewAnimClass : '',
               row.isNew && row.direction === 'IN'  ? 'flash-in'  : '',
               row.isNew && row.direction === 'OUT' ? 'flash-out' : '',
               'flex items-center px-3 py-2 border-b border-qubic-border/30'
             ]">
          <span class="w-20 text-gray-400">{{ row.time }}</span>
          <span class="w-16">
            <span v-if="row.direction === 'IN'"  class="text-green-400">▲ IN</span>
            <span v-else                          class="text-red-400">▼ OUT</span>
          </span>
          <span class="font-mono">{{ row.amount }} QU</span>
        </div>
      </div>
    </div>

    <!-- Währung -->
    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">Währung</h3>
      <div class="flex gap-2">
        <button v-for="[val, lbl, flag] in [['EUR','Euro','€'],['USD','US-Dollar','$']]"
                :key="val"
                :class="['btn-ghost text-xs py-1', store.currency === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setCurrency(val)">
          <span class="mr-1">{{ flag }}</span>{{ lbl }}
        </button>
      </div>
    </div>

    <!-- Schriftgröße -->
    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">Schriftgröße</h3>
      <div class="flex items-center gap-3 flex-wrap">
        <button v-for="[val, lbl] in [['85','Klein'],['100','Normal'],['115','Groß'],['130','Sehr groß']]"
                :key="val"
                :class="['btn-ghost text-xs py-1', store.fontSize === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setFontSize(val)">
          {{ lbl }}
        </button>
        <span class="text-xs text-gray-500 ml-2">{{ store.fontSize }}%</span>
      </div>
    </div>

    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('settings.theme') }}</h3>
      <div class="flex gap-2">
        <button :class="['btn-ghost', store.theme === 'dark' && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="store.setTheme('dark')">{{ t('settings.dark') }}</button>
        <button :class="['btn-ghost', store.theme === 'light' && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="store.setTheme('light')">{{ t('settings.light') }}</button>
      </div>
    </div>

    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('settings.language') }}</h3>
      <div class="flex gap-2">
        <button :class="['btn-ghost', store.lang === 'de' && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="setLang('de')">Deutsch</button>
        <button :class="['btn-ghost', store.lang === 'en' && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="setLang('en')">English</button>
      </div>
    </div>

    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">Export</h3>
      <div class="flex items-center gap-3 mb-3">
        <label class="text-sm">{{ t('export.year') }}:</label>
        <input v-model.number="year" type="number" class="input w-32" />
      </div>
      <div class="flex gap-2">
        <a :href="exportUrl('cointracking', year)" class="btn">{{ t('export.cointracking') }}</a>
        <a :href="exportUrl('steuerberater', year)" class="btn">{{ t('export.steuerberater') }}</a>
      </div>
    </div>
  </div>
</template>
