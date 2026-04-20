<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTranslation } from 'i18next-vue'

const { t } = useTranslation()
const router = useRouter()
const open = ref(false)

const items = [
  { to: '/',         key: 'dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { to: '/wallets',  key: 'wallets',   icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
  { to: '/assets',   key: 'assets',    icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
  { to: '/nodes',    key: 'nodes',     icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2' },
  { to: '/stats',    key: 'stats',     icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { to: '/settings', key: 'settings',  icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]

function navigate(to) {
  open.value = false
  router.push(to)
}
</script>

<template>
  <nav class="border-b border-qubic-border bg-qubic-bg/80 relative z-30">
    <div class="w-full px-4 sm:px-6 lg:px-8">

      <!-- Desktop nav -->
      <ul class="hidden sm:flex gap-1">
        <li v-for="item in items" :key="item.to">
          <router-link
            :to="item.to"
            class="inline-block px-4 py-2 text-sm border-b-2 border-transparent hover:text-qubic-teal transition-colors"
            active-class="text-qubic-teal border-qubic-teal"
            exact-active-class="text-qubic-teal border-qubic-teal"
          >
            {{ t(`nav.${item.key}`) }}
          </router-link>
        </li>
      </ul>

      <!-- Mobile: burger button -->
      <div class="sm:hidden flex items-center justify-between py-2">
        <router-link to="/" class="text-sm font-semibold text-qubic-teal">
          {{ t(`nav.${items.find(i => i.to === $route?.path)?.key ?? 'dashboard'}`) }}
        </router-link>
        <button @click="open = !open"
                class="p-2 text-gray-400 hover:text-qubic-teal transition-colors"
                aria-label="Menü öffnen">
          <!-- Burger / Close icon -->
          <svg v-if="!open" xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile dropdown menu -->
    <div v-if="open"
         class="sm:hidden absolute top-full left-0 right-0 bg-qubic-card border-b border-qubic-border shadow-xl">
      <ul class="divide-y divide-qubic-border/40">
        <li v-for="item in items" :key="item.to">
          <button @click="navigate(item.to)"
                  class="w-full flex items-center gap-3 px-6 py-4 text-sm text-left hover:bg-qubic-teal/10 transition-colors"
                  :class="$route?.path === item.to ? 'text-qubic-teal' : 'text-gray-300'">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon"/>
            </svg>
            {{ t(`nav.${item.key}`) }}
          </button>
        </li>
      </ul>
    </div>

    <!-- Backdrop -->
    <div v-if="open" class="sm:hidden fixed inset-0 z-[-1]" @click="open = false" />
  </nav>
</template>
