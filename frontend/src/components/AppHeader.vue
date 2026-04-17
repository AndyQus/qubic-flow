<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()
</script>

<template>
  <header class="border-b border-qubic-border bg-qubic-card/40 backdrop-blur-glass">
    <div class="container mx-auto px-4 py-4 flex items-center justify-between max-w-7xl">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-qubic-teal/20 border border-qubic-teal/40 flex items-center justify-center">
          <span class="text-qubic-teal font-bold">Q</span>
        </div>
        <div>
          <h1 class="text-lg font-semibold">{{ t('app.title') }}</h1>
          <p class="text-xs text-gray-400">{{ t('app.subtitle') }}</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="pill">
          <span class="w-2 h-2 rounded-full mr-1.5"
                :class="store.activeNode ? 'bg-green-500' : 'bg-red-500'"></span>
          {{ store.activeNode ? t('status.connected') : t('status.no_node') }}
        </span>
      </div>
    </div>
  </header>
</template>
