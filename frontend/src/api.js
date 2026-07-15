const BASE = '/api/v1'

function buildQuery(params) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(item => q.append(k, item))
    else if (v !== undefined && v !== null && v !== '') q.append(k, v)
  }
  return q.toString()
}

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  if (r.status === 204) return null
  return r.json()
}

export const api = {
  wallets: {
    list: () => req('/wallets'),
    create: (data) => req('/wallets', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => req(`/wallets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id) => req(`/wallets/${id}`, { method: 'DELETE' }),
    resyncTx: (id) => req(`/wallets/${id}/resync-tx`, { method: 'POST' }),
    resyncAll: () => req('/wallets/resync-all', { method: 'POST' }),
    assets: (id) => req(`/wallets/${id}/assets`),
    assetsSummary: () => req('/wallets/assets-summary'),
  },
  events: {
    list: (params = {}) => {
      const q = buildQuery(params)
      return req(`/events${q ? '?' + q : ''}`)
    },
    count: (params = {}) => {
      const q = buildQuery(params)
      return req(`/events/count${q ? '?' + q : ''}`)
    },
    filterOptions: (walletId, walletIds = []) => {
      if (walletIds.length) {
        const q = buildQuery({ wallet_ids: walletIds })
        return req(`/events/filter-options?${q}`)
      }
      return req(`/events/filter-options${walletId ? `?wallet_id=${walletId}` : ''}`)
    },
    donationCheck: () => req('/events/donation-check'),
    donationSuppression: () => req('/events/donation-suppression'),
    donationTop: () => req('/events/donation-top'),
    donationHistory: (mineOnly = false) => req(`/events/donation-history${mineOnly ? '?mine_only=true' : ''}`),
    updateNote: (eventId, walletId, note) => req(`/events/${eventId}/note`, {
      method: 'PATCH',
      body: JSON.stringify({ wallet_id: walletId, note: note || null }),
    }),
  },
  nodes: {
    list: () => req('/nodes'),
    create: (data) => req('/nodes', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => req(`/nodes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id) => req(`/nodes/${id}`, { method: 'DELETE' }),
    reorder: (order) => req('/nodes/reorder', { method: 'PUT', body: JSON.stringify({ order }) }),
    toggle:  (id) => req(`/nodes/${id}/toggle`, { method: 'PATCH' }),
    logs: () => req('/nodes/logs'),
    logErrorCheck: () => req('/nodes/logs/error-check'),
    checkNow: (id) => req(`/nodes/${id}/check-now`, { method: 'POST' }),
    syncNow: () => req('/nodes/sync-now', { method: 'POST' }),
    diagnose: () => req('/nodes/diagnose', { method: 'POST' }),
  },
  stats: {
    current:  (walletIds = []) => {
      const q = buildQuery({ wallet_ids: walletIds })
      return req(`/stats/current${q ? '?' + q : ''}`)
    },
    snapshots: () => req('/stats/snapshots'),
    history:  (groupBy = 'week', walletIds = []) => {
      const q = buildQuery({ group_by: groupBy, wallet_ids: walletIds })
      return req(`/stats/history${q ? '?' + q : ''}`)
    },
    epochs:   () => req('/stats/epochs'),
    portfolioHistory: (walletIds = []) => {
      const q = buildQuery({ wallet_ids: walletIds })
      return req(`/stats/portfolio-history${q ? '?' + q : ''}`)
    },
  },
  labels: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return req(`/labels${q ? '?' + q : ''}`)
    },
  },
  backup: {
    export: () => req('/backup'),
    restore: (data) => req('/backup/restore', { method: 'POST', body: JSON.stringify(data) }),
  },
  notifications: {
    getSettings: () => req('/notifications/settings'),
    saveSettings: (data) => req('/notifications/settings', { method: 'PUT', body: JSON.stringify(data) }),
    test: () => req('/notifications/test', { method: 'POST' }),
  },
  metrics: () => req('/metrics'),
  health: () => req('/health'),
  balanceHistory: {
    getSettings: () => req('/balance-history/settings'),
    saveSettings: (data) => req('/balance-history/settings', { method: 'PUT', body: JSON.stringify(data) }),
    overview: (kind) => req(`/balance-history/overview?kind=${kind}`),
    capture: (kind = 'hourly') => req('/balance-history/capture', { method: 'POST', body: JSON.stringify({ kind }) }),
    editSnapshot: (id, data) => req(`/balance-history/snapshots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    saveAnnotation: (data) => req('/balance-history/annotations', { method: 'PATCH', body: JSON.stringify(data) }),
    createRow: (data) => req('/balance-history/rows', { method: 'POST', body: JSON.stringify(data) }),
    deleteRow: (kind, bucket) => req(`/balance-history/rows?${buildQuery({ kind, bucket })}`, { method: 'DELETE' }),
    ownerLedger: (owner, kind, limit = 200, offset = 0) => req(`/balance-history/owner-ledger?${buildQuery({ owner, kind, limit, offset })}`),
    transfers: (kind, limit = 200, offset = 0) => req(`/balance-history/transfers?${buildQuery({ kind, limit, offset })}`),
    transactions: (kind, limit = 200, offset = 0) => req(`/balance-history/transactions?${buildQuery({ kind, limit, offset })}`),
    rebuildExports: () => req('/balance-history/export/rebuild', { method: 'POST' }),
    resetSeries: (kind) => req(`/balance-history/series/${kind}`, { method: 'DELETE' }),
  },
  tax: {
    getSettings: () => req('/tax/settings'),
    saveSettings: (data) => req('/tax/settings', { method: 'PUT', body: JSON.stringify(data) }),
    getCountries: () => req('/tax/countries'),
    getOpeningPositions: (walletId) => req(`/tax/opening-positions${walletId ? `?wallet_id=${walletId}` : ''}`),
    createOpeningPosition: (data) => req('/tax/opening-positions', { method: 'POST', body: JSON.stringify(data) }),
    deleteOpeningPosition: (id) => req(`/tax/opening-positions/${id}`, { method: 'DELETE' }),
    getReport: (params = {}) => {
      const q = buildQuery(params)
      return req(`/tax/report${q ? '?' + q : ''}`)
    },
    getPriceForDate: (date) => req(`/tax/price?date=${date}`),
  },
}

export function exportUrl(kind, year) {
  const y = year ? `?year=${year}` : ''
  return `${BASE}/export/${kind}${y}`
}
