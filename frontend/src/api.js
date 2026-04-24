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
    filterOptions: (walletId) => req(`/events/filter-options?wallet_id=${walletId}`),
  },
  nodes: {
    list: () => req('/nodes'),
    create: (data) => req('/nodes', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => req(`/nodes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id) => req(`/nodes/${id}`, { method: 'DELETE' }),
    reorder: (order) => req('/nodes/reorder', { method: 'PUT', body: JSON.stringify({ order }) }),
    toggle:  (id) => req(`/nodes/${id}/toggle`, { method: 'PATCH' }),
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
  metrics: () => req('/metrics'),
  health: () => req('/health'),
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
