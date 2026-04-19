<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import logoUrl from '../assets/logo-v1.svg'

const store = useAppStore()
const { t } = useTranslation()
</script>

<template>
  <header class="border-b border-qubic-border bg-qubic-card/40 backdrop-blur-glass">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
      <router-link to="/">
        <img :src="logoUrl" alt="QubicFlow" class="h-[72px] w-auto" />
      </router-link>
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
