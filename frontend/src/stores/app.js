import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const animation = ref(localStorage.getItem('animation') || 'beam-drop')
  const theme = ref(localStorage.getItem('theme') || 'dark')
  const lang = ref(localStorage.getItem('lang') || 'de')
  const walletFilter = ref('all')
  const wallets = ref([])
  const events = ref([])
  const nodes = ref([])
  const wsConnected = ref(false)

  const filteredWallets = computed(() => {
    if (walletFilter.value === 'all') return wallets.value
    return wallets.value.filter(w => w.wallet_type === walletFilter.value.toUpperCase())
  })

  const activeNode = computed(() => nodes.value.find(n => n.health_status === 'ONLINE'))

  function setAnimation(a) { animation.value = a; localStorage.setItem('animation', a) }
  function setTheme(t) {
    theme.value = t
    localStorage.setItem('theme', t)
    document.documentElement.classList.toggle('light', t === 'light')
    document.documentElement.classList.toggle('dark', t === 'dark')
  }
  function setLang(l) { lang.value = l; localStorage.setItem('lang', l) }

  function prependEvent(ev) {
    events.value.unshift(ev)
    if (events.value.length > 500) events.value.pop()
  }

  return {
    animation, theme, lang, walletFilter,
    wallets, events, nodes, wsConnected,
    filteredWallets, activeNode,
    setAnimation, setTheme, setLang, prependEvent,
  }
})
