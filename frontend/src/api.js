const BASE = '/api/v1'

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
      const q = new URLSearchParams(params).toString()
      return req(`/events${q ? '?' + q : ''}`)
    },
    count: (params = {}) => {
      const q = new URLSearchParams(params).toString()
      return req(`/events/count${q ? '?' + q : ''}`)
    },
  },
  nodes: {
    list: () => req('/nodes'),
    create: (data) => req('/nodes', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => req(`/nodes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id) => req(`/nodes/${id}`, { method: 'DELETE' }),
    reorder: (order) => req('/nodes/reorder', { method: 'PUT', body: JSON.stringify({ order }) }),
  },
  stats: {
    current:  () => req('/stats/current'),
    snapshots: () => req('/stats/snapshots'),
    history:  (groupBy = 'week') => req(`/stats/history?group_by=${groupBy}`),
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
