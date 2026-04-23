import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const animation  = ref(localStorage.getItem('animation')  || 'beam-drop')
  const moneyAnim   = ref(localStorage.getItem('moneyAnim')   || 'floating-coins')
  const moneySound  = ref(localStorage.getItem('moneySound')  === 'true')
  const soundStyle  = ref(localStorage.getItem('soundStyle')  || 'kaching')
  const theme = ref(localStorage.getItem('theme') || 'dark')
  const lang = ref(localStorage.getItem('lang') || 'en')
  const fontSize = ref(localStorage.getItem('fontSize') || '115')
  const hideAddresses = ref(localStorage.getItem('hideAddresses') === 'true')
  const currency = ref(localStorage.getItem('currency') || 'USD')
  const walletFilter = ref('all')
  const wallets = ref([])
  const events = ref([])
  const nodes = ref([])
  const wsConnected = ref(false)
  const newEventIds = ref([])

  const locale = computed(() => lang.value === 'de' ? 'de-DE' : 'en-US')

  const filteredWallets = computed(() => {
    if (walletFilter.value === 'all') return wallets.value
    return wallets.value.filter(w => w.wallet_type === walletFilter.value.toUpperCase())
  })

  const activeNode = computed(() => nodes.value.find(n => n.is_active && n.health_status === 'ONLINE'))

  function setAnimation(a)  { animation.value  = a; localStorage.setItem('animation',  a) }
  function setMoneyAnim(a)   { moneyAnim.value   = a; localStorage.setItem('moneyAnim',   a) }
  function setMoneySound(v)  { moneySound.value  = v; localStorage.setItem('moneySound',  String(v)) }
  function setSoundStyle(s)  { soundStyle.value  = s; localStorage.setItem('soundStyle',  s) }
  function toggleHideAddresses() {
    hideAddresses.value = !hideAddresses.value
    localStorage.setItem('hideAddresses', hideAddresses.value)
  }
  function setCurrency(c) { currency.value = c; localStorage.setItem('currency', c) }
  function setFontSize(s) {
    fontSize.value = s
    localStorage.setItem('fontSize', s)
    document.documentElement.style.fontSize = s + '%'
  }
  function setTheme(t) {
    theme.value = t
    localStorage.setItem('theme', t)
    document.documentElement.classList.toggle('light', t === 'light')
    document.documentElement.classList.toggle('dark', t === 'dark')
  }

  function setLang(l) { lang.value = l; localStorage.setItem('lang', l) }

  const DASHBOARD_LIMIT = 10

  function prependEvent(ev) {
    events.value.unshift(ev)
    if (events.value.length > DASHBOARD_LIMIT) events.value.splice(DASHBOARD_LIMIT)
    newEventIds.value.push(ev.id)
    setTimeout(() => {
      const idx = newEventIds.value.indexOf(ev.id)
      if (idx >= 0) newEventIds.value.splice(idx, 1)
    }, 20_000)
  }

  function simulateEvent() {
    const directions = ['IN', 'OUT']
    const dir = directions[Math.floor(Math.random() * 2)]
    const ownedId = wallets.value[0]?.id || 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    const externalId = 'ZZZZZZZZBBBBBBBBCCCCCCCCDDDDDDDDEEEEEEEEFFFFFFFFGGGGGGGGHHHHHH'
    prependEvent({
      id: `sim_${Date.now()}`,
      timestamp: new Date().toISOString(),
      source_address: dir === 'OUT' ? ownedId : externalId,
      destination_addr: dir === 'IN' ? ownedId : externalId,
      amount_qubic: Math.floor(Math.random() * 9000) + 500,
      qubic_eur_rate: 0.000065,
      is_internal: 0,
      wallet_id: ownedId,
      source_type: 'EVENT',
    })
  }

  return {
    animation, moneyAnim, moneySound, soundStyle,
    theme, lang, fontSize, hideAddresses, currency, walletFilter,
    wallets, events, nodes, wsConnected, newEventIds,
    locale, filteredWallets, activeNode,
    setAnimation, setMoneyAnim, setMoneySound, setSoundStyle,
    setTheme, setLang, setFontSize, toggleHideAddresses, setCurrency, prependEvent, simulateEvent,
  }
})
