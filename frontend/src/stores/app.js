import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const animation = ref(localStorage.getItem('animation') || 'beam-drop')
  const theme = ref(localStorage.getItem('theme') || 'dark')
  const lang = ref(localStorage.getItem('lang') || 'de')
  const fontSize = ref(localStorage.getItem('fontSize') || '100')
  const walletFilter = ref('all')
  const wallets = ref([])
  const events = ref([])
  const nodes = ref([])
  const wsConnected = ref(false)
  const newEventIds = ref([])

  const filteredWallets = computed(() => {
    if (walletFilter.value === 'all') return wallets.value
    return wallets.value.filter(w => w.wallet_type === walletFilter.value.toUpperCase())
  })

  const activeNode = computed(() => nodes.value.find(n => n.health_status === 'ONLINE'))

  function setAnimation(a) { animation.value = a; localStorage.setItem('animation', a) }
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

  function prependEvent(ev) {
    events.value.unshift(ev)
    newEventIds.value.push(ev.id)
    setTimeout(() => {
      const idx = newEventIds.value.indexOf(ev.id)
      if (idx >= 0) newEventIds.value.splice(idx, 1)
    }, 2000)
    if (events.value.length > 500) events.value.pop()
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
    animation, theme, lang, fontSize, walletFilter,
    wallets, events, nodes, wsConnected, newEventIds,
    filteredWallets, activeNode,
    setAnimation, setTheme, setLang, setFontSize, prependEvent, simulateEvent,
  }
})
