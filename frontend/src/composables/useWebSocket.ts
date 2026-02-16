import { ref, onUnmounted, type Ref } from 'vue'

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface WebSocketMessage {
  type: string
  payload: unknown
  timestamp: number
}

export interface UseWebSocketOptions {
  autoConnect?: boolean
  reconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  onOpen?: (event: Event) => void
  onClose?: (event: CloseEvent) => void
  onError?: (event: Event) => void
  onMessage?: (data: WebSocketMessage) => void
}

export interface UseWebSocketReturn {
  status: Ref<WebSocketStatus>
  data: Ref<WebSocketMessage | null>
  error: Ref<string | null>
  connect: () => void
  disconnect: () => void
  send: (message: WebSocketMessage) => boolean
  isConnected: Ref<boolean>
}

export function useWebSocket(
  url: string,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    autoConnect = true,
    reconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    onOpen,
    onClose,
    onError,
    onMessage,
  } = options

  const status = ref<WebSocketStatus>('disconnected')
  const data = ref<WebSocketMessage | null>(null)
  const error = ref<string | null>(null)
  const isConnected = ref(false)

  let socket: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: number | null = null

  function connect() {
    if (socket?.readyState === WebSocket.OPEN) {
      return
    }

    status.value = 'connecting'
    error.value = null

    try {
      socket = new WebSocket(url)

      socket.onopen = (event) => {
        status.value = 'connected'
        isConnected.value = true
        reconnectAttempts = 0
        onOpen?.(event)
      }

      socket.onclose = (event) => {
        status.value = 'disconnected'
        isConnected.value = false
        onClose?.(event)

        // Attempt to reconnect
        if (reconnect && reconnectAttempts < maxReconnectAttempts) {
          scheduleReconnect()
        }
      }

      socket.onerror = (event) => {
        status.value = 'error'
        error.value = 'WebSocket connection error'
        onError?.(event)
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage
          data.value = message
          onMessage?.(message)
        } catch {
          // If not JSON, wrap in a message object
          data.value = {
            type: 'raw',
            payload: event.data,
            timestamp: Date.now(),
          }
        }
      }
    } catch (e) {
      status.value = 'error'
      error.value = e instanceof Error ? e.message : 'Failed to create WebSocket'
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    reconnectAttempts = maxReconnectAttempts // Prevent reconnection

    if (socket) {
      socket.close()
      socket = null
    }

    status.value = 'disconnected'
    isConnected.value = false
  }

  function send(message: WebSocketMessage): boolean {
    if (socket?.readyState !== WebSocket.OPEN) {
      error.value = 'WebSocket is not connected'
      return false
    }

    try {
      socket.send(JSON.stringify(message))
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to send message'
      return false
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }

    reconnectAttempts++
    const delay = reconnectInterval * Math.pow(1.5, reconnectAttempts - 1)

    reconnectTimer = window.setTimeout(() => {
      connect()
    }, delay)
  }

  // Auto connect on mount
  if (autoConnect) {
    connect()
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    data,
    error,
    connect,
    disconnect,
    send,
    isConnected,
  }
}

// WebSocket connection manager for global state
class WebSocketManager {
  private connections: Map<string, WebSocket> = new Map()
  private subscribers: Map<string, Set<(data: WebSocketMessage) => void>> = new Map()

  connect(url: string, key: string = 'default'): WebSocket {
    if (this.connections.has(key)) {
      const existing = this.connections.get(key)!
      if (existing.readyState === WebSocket.OPEN) {
        return existing
      }
    }

    const socket = new WebSocket(url)
    this.connections.set(key, socket)

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage
        this.notifySubscribers(key, message)
      } catch {
        this.notifySubscribers(key, {
          type: 'raw',
          payload: event.data,
          timestamp: Date.now(),
        })
      }
    }

    return socket
  }

  disconnect(key: string = 'default') {
    const socket = this.connections.get(key)
    if (socket) {
      socket.close()
      this.connections.delete(key)
    }
  }

  disconnectAll() {
    this.connections.forEach((socket) => socket.close())
    this.connections.clear()
  }

  subscribe(key: string, callback: (data: WebSocketMessage) => void) {
    if (!this.subscribers.has(key)) {
      this.subscribers.set(key, new Set())
    }
    this.subscribers.get(key)!.add(callback)

    // Return unsubscribe function
    return () => {
      this.subscribers.get(key)?.delete(callback)
    }
  }

  private notifySubscribers(key: string, data: WebSocketMessage) {
    this.subscribers.get(key)?.forEach((callback) => callback(data))
  }

  send(key: string, message: WebSocketMessage): boolean {
    const socket = this.connections.get(key)
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message))
      return true
    }
    return false
  }

  getStatus(key: string = 'default'): WebSocketStatus {
    const socket = this.connections.get(key)
    if (!socket) return 'disconnected'

    switch (socket.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting'
      case WebSocket.OPEN:
        return 'connected'
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
      default:
        return 'disconnected'
    }
  }
}

// Singleton instance
export const wsManager = new WebSocketManager()
