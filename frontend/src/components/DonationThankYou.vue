<script setup>
import { onMounted } from 'vue'
import { useTranslation } from 'i18next-vue'
import { useDonationState } from '../composables/useDonationState'

const { t } = useTranslation()
const { isSuppressed, suppressedUntil, init } = useDonationState()

onMounted(init)
</script>

<template>
  <div v-if="isSuppressed" class="w-full bg-lime-400">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-1.5 flex items-center justify-center gap-2">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-black flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
      </svg>
      <p class="text-xs text-black font-medium">{{ t('donation.banner_suppressed') }} {{ suppressedUntil }}</p>
    </div>
  </div>
</template>
