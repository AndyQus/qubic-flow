import { useAppStore } from '../stores/app'

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
    if (addr) await navigator.clipboard.writeText(addr)
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
