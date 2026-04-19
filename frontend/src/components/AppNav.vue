<script setup>
import { useTranslation } from 'i18next-vue'
const { t } = useTranslation()

const items = [
  { to: '/', key: 'dashboard' },
  { to: '/wallets', key: 'wallets' },
  { to: '/assets', key: 'assets' },
  { to: '/nodes', key: 'nodes' },
  { to: '/stats', key: 'stats' },
  { to: '/settings', key: 'settings' },
]
</script>

<template>
  <nav class="border-b border-qubic-border bg-qubic-bg/80">
    <div class="container mx-auto px-4 max-w-7xl">
      <ul class="flex gap-1">
        <li v-for="item in items" :key="item.to">
          <router-link
            :to="item.to"
            class="inline-block px-4 py-3 text-sm border-b-2 border-transparent hover:text-qubic-teal transition-colors"
            active-class="text-qubic-teal border-qubic-teal"
            exact-active-class="text-qubic-teal border-qubic-teal"
          >
            {{ t(`nav.${item.key}`) }}
          </router-link>
        </li>
      </ul>
    </div>
  </nav>
</template>
