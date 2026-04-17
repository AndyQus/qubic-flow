<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import logoUrl from '../assets/logo-v1.svg'

const store = useAppStore()
const { t } = useTranslation()
</script>

<template>
  <header class="border-b border-qubic-border bg-qubic-card/40 backdrop-blur-glass">
    <div class="container mx-auto px-4 py-3 flex items-center justify-between max-w-7xl">
      <img :src="logoUrl" alt="QubicFlow" class="h-12 w-auto" />
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
