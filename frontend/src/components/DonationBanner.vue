<script setup>
import { onMounted } from 'vue'
import { useTranslation } from 'i18next-vue'
import { useRouter } from 'vue-router'
import { useDonationState } from '../composables/useDonationState'

const { t } = useTranslation()
const router = useRouter()
const { isVisible, showMiniTab, close, init } = useDonationState()

function goToSupport() {
  router.push('/support')
}

onMounted(init)
</script>

<template>
  <!-- Full banner -->
  <div v-if="isVisible"
       class="w-full bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 text-white shadow-lg">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-3 flex flex-col sm:flex-row items-start sm:items-center gap-3">
      <div class="flex-1 min-w-0">
        <p class="font-semibold text-sm leading-snug">{{ t('donation.banner_title') }}</p>
        <p class="text-xs text-amber-100 mt-0.5 leading-snug">{{ t('donation.banner_text') }}</p>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button
          @click="goToSupport"
          class="px-4 py-1.5 bg-white text-amber-600 font-semibold text-xs rounded-full hover:bg-amber-50 transition-colors whitespace-nowrap shadow"
        >
          {{ t('donation.banner_cta') }}
        </button>
        <button
          @click="close"
          class="p-1.5 text-amber-100 hover:text-white transition-colors"
          :aria-label="t('donation.banner_dismiss')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Mini tab after close -->
  <div v-else-if="showMiniTab"
       class="w-full bg-amber-500/10 border-b border-amber-500/20">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-1 flex items-center gap-2">
      <button @click="goToSupport" class="flex items-center gap-1.5 text-amber-500 hover:text-amber-400 transition-colors text-xs font-medium">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
        </svg>
        {{ t('donation.tab_reopen') }}
      </button>
    </div>
  </div>
</template>
