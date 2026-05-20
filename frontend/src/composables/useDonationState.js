import { ref, computed } from 'vue'
import { api } from '../api'

const today = new Date().toISOString().slice(0, 10)
const STORAGE_KEY_CLOSED = 'donation_closed_date'
const STORAGE_KEY_SUPPRESSED = 'donation_suppressed_until'

const closedToday = ref(false)
const suppressedUntil = ref(null)
const totalQu = ref(0)
let initialized = false

// Debug overrides — only used in DEV builds
const debugSuppressedUntil = ref(null)
const debugTotalQu = ref(null)

export function setDebugSuppression(value) {
  if (!import.meta.env.DEV) return
  debugSuppressedUntil.value = value
}

export function setDebugTotalQu(value) {
  if (!import.meta.env.DEV) return
  debugTotalQu.value = value
}

export const DONATION_RANKS = [
  { icon: '⚡', name: 'Quantum Spark',  color: '#a78bfa', minQu: 1_000_000,     descDe: 'Jeder Funke entzündet ein Feuer',    descEn: 'Every spark starts a fire' },
  { icon: '🗡️', name: 'Qubic Knight',   color: '#38bdf8', minQu: 10_000_000,    descDe: 'Ein Kämpfer für das Ökosystem',      descEn: 'A warrior for the ecosystem' },
  { icon: '⚔️', name: 'Crypto Avenger', color: '#4EE0FC', minQu: 50_000_000,    descDe: 'Verteidiger der Dezentralisierung',  descEn: 'Defending decentralization' },
  { icon: '🛡️', name: 'Block Guardian', color: '#4ade80', minQu: 100_000_000,   descDe: 'Beschützer des Netzwerks',           descEn: 'Protecting the network' },
  { icon: '💎', name: 'Diamond Node',   color: '#67e8f9', minQu: 500_000_000,   descDe: 'Selten und unzerstörbar',            descEn: 'Rare and indestructible' },
  { icon: '👑', name: 'Chain Legend',   color: '#FFD700', minQu: 1_000_000_000, descDe: 'Für immer verewigt',                 descEn: 'Forever immortalized' },
]

export function getDonorRank(qu) {
  for (let i = DONATION_RANKS.length - 1; i >= 0; i--) {
    if (qu >= DONATION_RANKS[i].minQu) return DONATION_RANKS[i]
  }
  return null
}

export function useDonationState() {
  const effectiveSuppressed = computed(() => debugSuppressedUntil.value ?? suppressedUntil.value)
  const effectiveTotalQu = computed(() => debugTotalQu.value ?? totalQu.value)
  const isVisible = computed(() => !effectiveSuppressed.value && !closedToday.value)
  const isSuppressed = computed(() => !!effectiveSuppressed.value)
  const showMiniTab = computed(() => !isSuppressed.value && closedToday.value)
  const donorRank = computed(() => getDonorRank(effectiveTotalQu.value))

  function close() {
    localStorage.setItem(STORAGE_KEY_CLOSED, today)
    closedToday.value = true
  }

  async function init() {
    if (initialized) return
    initialized = true

    const closed = localStorage.getItem(STORAGE_KEY_CLOSED)
    closedToday.value = closed === today

    // Run suppression check and full donation check in parallel
    const [suppressionRes, checkRes] = await Promise.allSettled([
      api.events.donationSuppression(),
      api.events.donationCheck(),
    ])

    // Full check: extract rank + use for suppression (most authoritative)
    if (checkRes.status === 'fulfilled') {
      const data = checkRes.value
      if (data.total_qu) totalQu.value = data.total_qu
      if (data.suppressed_until && data.suppressed_until > today) {
        localStorage.setItem(STORAGE_KEY_SUPPRESSED, data.suppressed_until)
        suppressedUntil.value = data.suppressed_until
        return
      }
    }

    // Fallback: server-side cached suppression
    if (suppressionRes.status === 'fulfilled') {
      const stored = suppressionRes.value
      if (stored.suppressed_until && stored.suppressed_until > today) {
        suppressedUntil.value = stored.suppressed_until
        return
      }
    }

    // Last fallback: localStorage
    const sup = localStorage.getItem(STORAGE_KEY_SUPPRESSED)
    if (sup && sup > today) suppressedUntil.value = sup
  }

  return { isVisible, isSuppressed, showMiniTab, close, init, suppressedUntil: effectiveSuppressed, donorRank, totalQu: effectiveTotalQu }
}
