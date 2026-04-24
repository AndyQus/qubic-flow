/**
 * Unit tests for composables/useQubicUtils.js
 * Pure-function tests — URL builders and address formatting.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '../../stores/app'
import { useQubicUtils } from '../../composables/useQubicUtils'

const ADDR = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz'
const TX_ID = 'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefgh'
const TICK = 12345678

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

// ------------------------------------------------------------------ URLs --

describe('explorerUrl', () => {
  it('builds the correct address explorer URL', () => {
    const { explorerUrl } = useQubicUtils()
    expect(explorerUrl(ADDR)).toBe(`https://explorer.qubic.org/network/address/${ADDR}`)
  })
})

describe('txUrl', () => {
  it('builds the correct transaction URL', () => {
    const { txUrl } = useQubicUtils()
    expect(txUrl(TX_ID)).toBe(`https://explorer.qubic.org/network/tx/${TX_ID}`)
  })
})

describe('tickUrl', () => {
  it('builds the correct tick URL', () => {
    const { tickUrl } = useQubicUtils()
    expect(tickUrl(TICK)).toBe(`https://explorer.qubic.org/network/tick/${TICK}`)
  })
})

// ------------------------------------------------------------------ shortAddr --

describe('shortAddr', () => {
  it('returns em-dash for null input', () => {
    const { shortAddr } = useQubicUtils()
    expect(shortAddr(null)).toBe('—')
    expect(shortAddr('')).toBe('—')
    expect(shortAddr(undefined)).toBe('—')
  })

  it('truncates long address to first5…last5', () => {
    const { shortAddr } = useQubicUtils()
    const addr = 'AAAAA_MIDDLE_PART_BBBBB'
    const result = shortAddr(addr)
    expect(result).toBe('AAAAA…BBBBB')
  })

  it('returns address unchanged when 10 chars or fewer', () => {
    const { shortAddr } = useQubicUtils()
    expect(shortAddr('SHORT')).toBe('SHORT')
    expect(shortAddr('EXACTLY10X')).toBe('EXACTLY10X')
  })

  it('returns privacy mask when hideAddresses is true', () => {
    const store = useAppStore()
    store.hideAddresses = true
    const { shortAddr } = useQubicUtils()
    expect(shortAddr(ADDR)).toBe('••••••••••••')
  })

  it('shows full short address even when not truncating', () => {
    const { shortAddr } = useQubicUtils()
    expect(shortAddr('ABC')).toBe('ABC')
  })
})

// ------------------------------------------------------------------ maskLabel --

describe('maskLabel', () => {
  it('returns original label when hideAddresses is false', () => {
    const store = useAppStore()
    store.hideAddresses = false
    const { maskLabel } = useQubicUtils()
    expect(maskLabel('My Wallet', ADDR)).toBe('My Wallet')
  })

  it('returns Wallet N when hideAddresses is true', () => {
    const store = useAppStore()
    store.hideAddresses = true
    const { maskLabel } = useQubicUtils()
    const result = maskLabel('My Wallet', ADDR)
    expect(result).toMatch(/^Wallet \d+$/)
  })

  it('is deterministic — same address always returns same label', () => {
    const store = useAppStore()
    store.hideAddresses = true
    const { maskLabel } = useQubicUtils()
    const r1 = maskLabel('Any Label', ADDR)
    const r2 = maskLabel('Different Label', ADDR)
    expect(r1).toBe(r2)
  })

  it('Wallet N is in range 0-100', () => {
    const store = useAppStore()
    store.hideAddresses = true
    const { maskLabel } = useQubicUtils()
    const result = maskLabel('x', ADDR)
    const n = parseInt(result.replace('Wallet ', ''), 10)
    expect(n).toBeGreaterThanOrEqual(0)
    expect(n).toBeLessThanOrEqual(100)
  })
})
