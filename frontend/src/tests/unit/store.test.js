/**
 * Unit tests for stores/app.js (Pinia store)
 * Covers computed properties, state mutations, and localStorage persistence.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '../../stores/app'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

// ------------------------------------------------------------------ locale --

describe('locale computed', () => {
  it('returns de-DE when lang is de', () => {
    const store = useAppStore()
    store.setLang('de')
    expect(store.locale).toBe('de-DE')
  })

  it('returns en-US when lang is en', () => {
    const store = useAppStore()
    store.setLang('en')
    expect(store.locale).toBe('en-US')
  })
})

// ------------------------------------------------------------------ filteredWallets --

describe('filteredWallets computed', () => {
  const walletPrivate = { id: 'w1', wallet_type: 'PRIVATE', label: 'P' }
  const walletBusiness = { id: 'w2', wallet_type: 'BUSINESS', label: 'B' }

  it('returns all wallets when filter is "all"', () => {
    const store = useAppStore()
    store.wallets = [walletPrivate, walletBusiness]
    store.walletFilter = 'all'
    expect(store.filteredWallets).toHaveLength(2)
  })

  it('filters to PRIVATE wallets only', () => {
    const store = useAppStore()
    store.wallets = [walletPrivate, walletBusiness]
    store.walletFilter = 'private'
    expect(store.filteredWallets).toHaveLength(1)
    expect(store.filteredWallets[0].id).toBe('w1')
  })

  it('filters to BUSINESS wallets only', () => {
    const store = useAppStore()
    store.wallets = [walletPrivate, walletBusiness]
    store.walletFilter = 'business'
    expect(store.filteredWallets).toHaveLength(1)
    expect(store.filteredWallets[0].id).toBe('w2')
  })

  it('returns empty array when no wallets match filter', () => {
    const store = useAppStore()
    store.wallets = [walletPrivate]
    store.walletFilter = 'business'
    expect(store.filteredWallets).toHaveLength(0)
  })
})

// ------------------------------------------------------------------ activeNode --

describe('activeNode computed', () => {
  it('returns online active node', () => {
    const store = useAppStore()
    store.nodes = [
      { id: 1, is_active: true, health_status: 'ONLINE' },
      { id: 2, is_active: true, health_status: 'OFFLINE' },
    ]
    expect(store.activeNode?.id).toBe(1)
  })

  it('returns undefined when no active online node exists', () => {
    const store = useAppStore()
    store.nodes = [{ id: 1, is_active: false, health_status: 'ONLINE' }]
    expect(store.activeNode).toBeUndefined()
  })

  it('returns undefined for empty nodes list', () => {
    const store = useAppStore()
    store.nodes = []
    expect(store.activeNode).toBeUndefined()
  })
})

// ------------------------------------------------------------------ prependEvent --

describe('prependEvent', () => {
  it('adds event to front of events array', () => {
    const store = useAppStore()
    store.events = [{ id: 'old' }]
    store.prependEvent({ id: 'new', timestamp: '' })
    expect(store.events[0].id).toBe('new')
  })

  it('truncates events to DASHBOARD_LIMIT=10', () => {
    const store = useAppStore()
    store.events = Array.from({ length: 10 }, (_, i) => ({ id: `e${i}` }))
    store.prependEvent({ id: 'new11', timestamp: '' })
    expect(store.events).toHaveLength(10)
    expect(store.events[0].id).toBe('new11')
  })

  it('adds event id to newEventIds', () => {
    const store = useAppStore()
    store.prependEvent({ id: 'ev-flash', timestamp: '' })
    expect(store.newEventIds).toContain('ev-flash')
  })

  it('removes event id from newEventIds after 20s', async () => {
    vi.useFakeTimers()
    const store = useAppStore()
    store.prependEvent({ id: 'ev-timer', timestamp: '' })
    expect(store.newEventIds).toContain('ev-timer')
    vi.advanceTimersByTime(20_001)
    expect(store.newEventIds).not.toContain('ev-timer')
    vi.useRealTimers()
  })
})

// ------------------------------------------------------------------ localStorage persistence --

describe('localStorage persistence', () => {
  it('setCurrency saves to localStorage', () => {
    const store = useAppStore()
    store.setCurrency('EUR')
    expect(localStorage.getItem('currency')).toBe('EUR')
    expect(store.currency).toBe('EUR')
  })

  it('setLang saves to localStorage', () => {
    const store = useAppStore()
    store.setLang('de')
    expect(localStorage.getItem('lang')).toBe('de')
  })

  it('toggleHideAddresses flips the boolean and persists', () => {
    const store = useAppStore()
    const initial = store.hideAddresses
    store.toggleHideAddresses()
    expect(store.hideAddresses).toBe(!initial)
    expect(localStorage.getItem('hideAddresses')).toBe(String(!initial))
  })

  it('setAnimation saves to localStorage', () => {
    const store = useAppStore()
    store.setAnimation('slide-in')
    expect(localStorage.getItem('animation')).toBe('slide-in')
    expect(store.animation).toBe('slide-in')
  })
})
