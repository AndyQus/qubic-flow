import { ref, computed } from 'vue'
import { api } from '../api'

const today = new Date().toISOString().slice(0, 10)
const STORAGE_KEY_CLOSED = 'donation_closed_date'
const STORAGE_KEY_SUPPRESSED = 'donation_suppressed_until'

const closedToday = ref(false)
const suppressedUntil = ref(null)
let initialized = false

export function useDonationState() {
  const isVisible = computed(() => !suppressedUntil.value && !closedToday.value)
  const isSuppressed = computed(() => !!suppressedUntil.value)
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

  return { isVisible, isSuppressed, showMiniTab, close, init, suppressedUntil }
}
