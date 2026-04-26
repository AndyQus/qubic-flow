import { ref, computed } from 'vue'
import { api } from '../api'

const today = new Date().toISOString().slice(0, 10)
const STORAGE_KEY_CLOSED = 'donation_closed_date'
const STORAGE_KEY_SUPPRESSED = 'donation_suppressed_until'

const closedToday = ref(false)
const suppressedUntil = ref(null)
let initialized = false

// Debug override — only used in DEV builds
const debugSuppressedUntil = ref(null)

export function setDebugSuppression(value) {
  if (!import.meta.env.DEV) return
  debugSuppressedUntil.value = value
}

export function useDonationState() {
  const effectiveSuppressed = computed(() => debugSuppressedUntil.value ?? suppressedUntil.value)
  const isVisible = computed(() => !effectiveSuppressed.value && !closedToday.value)
  const isSuppressed = computed(() => !!effectiveSuppressed.value)
  const showMiniTab = computed(() => !isSuppressed.value && closedToday.value)

  function close() {
    localStorage.setItem(STORAGE_KEY_CLOSED, today)
    closedToday.value = true
  }

  async function init() {
    if (initialized) return
    initialized = true

    const closed = localStorage.getItem(STORAGE_KEY_CLOSED)
    closedToday.value = closed === today

    try {
      const stored = await api.events.donationSuppression()
      if (stored.suppressed_until && stored.suppressed_until > today) {
        suppressedUntil.value = stored.suppressed_until
        return
      }
    } catch {}

    const sup = localStorage.getItem(STORAGE_KEY_SUPPRESSED)
    if (sup && sup > today) {
      suppressedUntil.value = sup
      return
    }

    localStorage.removeItem(STORAGE_KEY_SUPPRESSED)
    try {
      const data = await api.events.donationCheck()
      if (data.suppressed_until) {
        localStorage.setItem(STORAGE_KEY_SUPPRESSED, data.suppressed_until)
        suppressedUntil.value = data.suppressed_until
      }
    } catch {}
  }

  return { isVisible, isSuppressed, showMiniTab, close, init, suppressedUntil: effectiveSuppressed }
}
