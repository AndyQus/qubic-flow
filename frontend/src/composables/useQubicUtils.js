import { ref } from 'vue'
import { useAppStore } from '../stores/app'
import i18next from 'i18next'

export const copyToast = ref('')
let _toastTimer = null

function _showToast(msg) {
  copyToast.value = msg
  clearTimeout(_toastTimer)
  _toastTimer = setTimeout(() => { copyToast.value = '' }, 2000)
}

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
    _showToast(s.length > 14 ? `${s.slice(0, 6)}…${s.slice(-6)}` : s)
  }

  // Copies a raw numeric/string value and shows a translated "Value copied" snackbar
  async function copyValue(val) {
    if (val == null) return
    const raw = String(val)
    try {
      await navigator.clipboard.writeText(raw)
    } catch {
      const el = document.createElement('textarea')
      el.value = raw
      el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    _showToast(i18next.t('common.copied_value'))
  }

  // locale-aware decimal formatting (replaces raw .toFixed())
  function fmtDecimal(n, decimals = 2) {
    if (n == null || isNaN(n)) return '—'
    return Number(n).toLocaleString(store.locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  // locale-aware rate formatting — strips trailing zeros, keeps precision
  function fmtRateLocale(n) {
    if (n == null || isNaN(n)) return '—'
    // format with full precision then strip trailing locale-specific zeros
    const formatted = Number(n).toLocaleString(store.locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 10,
    })
    return formatted
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

  return { explorerUrl, txUrl, tickUrl, copyAddress, copyValue, fmtDecimal, fmtRateLocale, shortAddr, maskLabel }
}
