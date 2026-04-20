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
  },
  labels: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return req(`/labels${q ? '?' + q : ''}`)
    },
  },
  metrics: () => req('/metrics'),
  health: () => req('/health'),
}

export function exportUrl(kind, year) {
  const y = year ? `?year=${year}` : ''
  return `${BASE}/export/${kind}${y}`
}
