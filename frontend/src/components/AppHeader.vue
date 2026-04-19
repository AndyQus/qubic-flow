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
         <!-- Adressen verbergen / anzeigen -->
        <button @click="store.toggleHideAddresses()"
                :title="store.hideAddresses ? 'Adressen anzeigen' : 'Adressen verbergen'"
                class="p-1.5 rounded-lg text-gray-400 hover:text-qubic-teal hover:bg-qubic-teal/10 transition-colors">
          <!-- Auge offen -->
          <svg v-if="!store.hideAddresses" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
          </svg>
          <!-- Auge geschlossen -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-qubic-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>
