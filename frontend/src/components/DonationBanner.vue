<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTranslation } from 'i18next-vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const { t } = useTranslation()
const router = useRouter()

const STORAGE_KEY_CLOSED = 'donation_closed_date'
const STORAGE_KEY_SUPPRESSED = 'donation_suppressed_until'

const today = new Date().toISOString().slice(0, 10)

const closedToday = ref(false)
const suppressedUntil = ref(null)
const minimized = ref(false)

const isVisible = computed(() => !suppressedUntil.value && !closedToday.value)
const isSuppressed = computed(() => !!suppressedUntil.value)
const showMiniTab = computed(() => !isSuppressed.value && closedToday.value)

function close() {
  localStorage.setItem(STORAGE_KEY_CLOSED, today)
  closedToday.value = true
}

function goToSupport() {
  router.push('/support')
}

onMounted(async () => {
  const closed = localStorage.getItem(STORAGE_KEY_CLOSED)
  closedToday.value = closed === today

  // First check DB (persisted, no blockchain call needed)
  try {
    const stored = await api.events.donationSuppression()
    if (stored.suppressed_until && stored.suppressed_until > today) {
      suppressedUntil.value = stored.suppressed_until
      return
    }
  } catch {}

  // Then check localStorage cache
  const sup = localStorage.getItem(STORAGE_KEY_SUPPRESSED)
  if (sup && sup > today) {
    suppressedUntil.value = sup
    return
  }

  // Finally do full blockchain check
  localStorage.removeItem(STORAGE_KEY_SUPPRESSED)
  try {
    const data = await api.events.donationCheck()
    if (data.suppressed_until) {
      localStorage.setItem(STORAGE_KEY_SUPPRESSED, data.suppressed_until)
      suppressedUntil.value = data.suppressed_until
    }
  } catch {}
})
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

  <!-- Suppressed notice -->
  <div v-else-if="isSuppressed"
       class="w-full bg-emerald-600/20 border-b border-emerald-600/30">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-1.5 flex items-center gap-2">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
      </svg>
      <p class="text-xs text-emerald-400">{{ t('donation.banner_suppressed') }} {{ suppressedUntil }}</p>
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
