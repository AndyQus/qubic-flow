import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

export function useWebSocket() {
  const store = useAppStore()
  let ws = null
  let retry = null

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/api/v1/ws`)
    ws.onopen = () => { store.wsConnected = true }
    ws.onclose = () => {
      store.wsConnected = false
      retry = setTimeout(connect, 3000)
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'event.new') store.prependEvent(msg.payload)
        else if (msg.type === 'node.health') {
          const idx = store.nodes.findIndex(n => n.id === msg.payload.node_id)
          if (idx >= 0) Object.assign(store.nodes[idx], msg.payload)
        }
        else if (msg.type === 'sync.node') {
          // The backend elected a (new) live-sync node. Reflect is_sync_active
          // across the node list so the header updates without a reload.
          for (const n of store.nodes) {
            n.is_sync_active = (n.id === msg.payload.node_id)
          }
        }
      } catch (err) {
        console.warn('WS message parse error', err)
      }
    }
  }

  onMounted(connect)
  onUnmounted(() => {
    if (retry) clearTimeout(retry)
    if (ws) ws.close()
  })
}
