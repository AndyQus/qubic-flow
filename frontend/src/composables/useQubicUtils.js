import { ref } from 'vue'
import { useAppStore } from '../stores/app'

export const copyToast = ref('')
let _toastTimer = null

export function useQubicUtils() {
  const store = useAppStore()

  function explorerUrl(addr) {
    return `https://explorer.qubic.org/network/address/${addr}`
  }

  function txUrl(id) {
    return `https://explorer.qubic.org/network/tx/${id}`
  }

  function tickUrl(tick) {
    return `https://explorer.qubic.org/network/tick/${tick}`
  }

  async function copyAddress(addr) {
    if (!addr) return
    try {
      await navigator.clipboard.writeText(addr)
    } catch {
      const el = document.createElement('textarea')
      el.value = addr
      el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    const s = String(addr)
    copyToast.value = s.length > 14 ? `${s.slice(0, 6)}…${s.slice(-6)}` : s
    clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => { copyToast.value = '' }, 2000)
  }

  function shortAddr(a) {
    if (!a) return '—'
    if (store.hideAddresses) return '••••••••••••'
    return a.length > 10 ? `${a.slice(0, 5)}…${a.slice(-5)}` : a
  }

  function maskLabel(label, id) {
    if (!store.hideAddresses) return label
    const n = id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 101
    return `Wallet ${n}`
  }

  return { explorerUrl, txUrl, tickUrl, copyAddress, shortAddr, maskLabel }
}
