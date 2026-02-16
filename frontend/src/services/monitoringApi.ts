/**
 * Monitoring API Service
 *
 * Client for the backend Monitoring API for real-time
 * system metrics, security events, and device status.
 */

const API_BASE = 'http://localhost:8000/api/monitoring'

// =============================================================================
// Types
// =============================================================================

export interface SystemMetric {
  name: string
  value: number
  unit: string
  trend: 'up' | 'down' | 'stable'
  status: 'normal' | 'warning' | 'critical'
}

export interface SecurityEvent {
  id: string
  timestamp: string
  type: 'auth' | 'tls' | 'encryption' | 'mesh' | 'privacy' | 'threat'
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  source: string
  message: string
  details?: Record<string, unknown>
}

export interface DeviceStatus {
  id: string
  name: string
  type: string
  protocol: string
  status: 'online' | 'offline' | 'warning' | 'compromised'
  last_seen: string
  signal_strength?: number
  battery_level?: number
}

export interface MeshNode {
  id: string
  role: 'coordinator' | 'router' | 'end_device'
  state: string
  neighbors: number
  messages_sent: number
  messages_received: number
}

export interface SecurityStats {
  auth_success: number
  auth_failure: number
  tls_handshakes: number
  encrypted_messages: number
  privacy_queries: number
  threats_blocked: number
}

export interface MonitoringSnapshot {
  timestamp: string
  simulation_state: 'idle' | 'running' | 'paused' | 'stopped' | 'completed' | 'error'
  metrics: SystemMetric[]
  security_stats: SecurityStats
  devices: DeviceStatus[]
  mesh_nodes: MeshNode[]
  recent_events: SecurityEvent[]
  is_live: boolean
}

// =============================================================================
// API Client
// =============================================================================

class MonitoringApiService {
  /**
   * Check if the monitoring API is available
   */
  async checkAvailability(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/stats`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Get complete monitoring snapshot
   */
  async getSnapshot(includeEvents = true, eventLimit = 50): Promise<MonitoringSnapshot> {
    const params = new URLSearchParams({
      include_events: String(includeEvents),
      event_limit: String(eventLimit),
    })
    const response = await fetch(`${API_BASE}/snapshot?${params}`)
    if (!response.ok) throw new Error(`Failed to get snapshot: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get current system metrics
   */
  async getMetrics(): Promise<SystemMetric[]> {
    const response = await fetch(`${API_BASE}/metrics`)
    if (!response.ok) throw new Error(`Failed to get metrics: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get device statuses
   */
  async getDevices(): Promise<DeviceStatus[]> {
    const response = await fetch(`${API_BASE}/devices`)
    if (!response.ok) throw new Error(`Failed to get devices: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get security events
   */
  async getEvents(options: {
    limit?: number
    severity?: string
    event_type?: string
  } = {}): Promise<SecurityEvent[]> {
    const params = new URLSearchParams()
    if (options.limit) params.set('limit', String(options.limit))
    if (options.severity) params.set('severity', options.severity)
    if (options.event_type) params.set('event_type', options.event_type)

    const url = params.toString() ? `${API_BASE}/events?${params}` : `${API_BASE}/events`
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Failed to get events: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get mesh network status
   */
  async getMeshNetwork(): Promise<MeshNode[]> {
    const response = await fetch(`${API_BASE}/mesh`)
    if (!response.ok) throw new Error(`Failed to get mesh: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get security statistics
   */
  async getSecurityStats(): Promise<SecurityStats> {
    const response = await fetch(`${API_BASE}/stats`)
    if (!response.ok) throw new Error(`Failed to get stats: ${response.statusText}`)
    return response.json()
  }
}

// Export singleton instance
export const monitoringApi = new MonitoringApiService()
