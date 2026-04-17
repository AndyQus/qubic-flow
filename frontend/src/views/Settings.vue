<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import i18next from 'i18next'
import { exportUrl } from '../api'
import { ref } from 'vue'

const store = useAppStore()
const { t } = useTranslation()
const year = ref(new Date().getFullYear())

function setLang(l) {
  store.setLang(l)
  i18next.changeLanguage(l)
}
</script>

<template>
  <div class="space-y-6">
    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('settings.animation') }}</h3>
      <div class="flex gap-2">
        <button v-for="a in ['push-down', 'slide-in', 'beam-drop']" :key="a"
                :class="['btn-ghost', store.animation === a && 'bg-qubic-teal/20 border-qubic-teal']"
                @click="store.setAnimation(a)">
          {{ t(`settings.${a.replace('-', '_')}`) }}
        </button>
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
