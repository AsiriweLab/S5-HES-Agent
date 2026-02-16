/**
 * Simulation API Service
 *
 * Frontend client for the backend SimulationEngine.
 * Connects to real IoT device simulation with telemetry data generation.
 */

const API_BASE = 'http://localhost:8000/api/simulation'

// =============================================================================
// Types
// =============================================================================

export interface HomeCreateRequest {
  name: string
  template?: string
  num_inhabitants?: number
  device_density?: number
  seed?: number
}

export interface CustomRoomConfig {
  id: string
  name: string
  type: string
  x: number
  y: number
  width: number
  height: number
  devices: {
    id: string
    name: string
    type: string
  }[]
}

export interface CustomInhabitantConfig {
  id: string
  name: string
  role: string
  age?: number
  schedule?: {
    wakeUp?: number
    sleep?: number
    workFromHome?: boolean
  }
}

export interface CustomHomeCreateRequest {
  name: string
  rooms: CustomRoomConfig[]
  inhabitants: CustomInhabitantConfig[]
}

export interface ThreatEventConfig {
  id: string
  type: string
  name: string
  startTime: number
  duration: number
  severity: string
  severityValue: number
  targetDevices: string[]
  description: string
  attackVector: string
}

export interface SimulationStartRequest {
  duration_hours: number
  time_compression?: number
  start_time?: string
  enable_threats?: boolean
  collect_all_events?: boolean
  threats?: ThreatEventConfig[]
}

export interface HomeResponse {
  id: string
  name: string
  template: string
  total_rooms: number
  total_devices: number
  total_inhabitants: number
  config: {
    total_area_sqm: number
    floors: number
    has_garage: boolean
    has_garden: boolean
  }
}

export interface SimulationStatusResponse {
  id: string
  state: 'idle' | 'running' | 'paused' | 'stopped' | 'completed' | 'error'
  simulation_time: string | null
  progress_percent: number
  total_ticks: number
  total_events: number
  events_by_type: Record<string, number>
  devices_simulated: number
  anomalies_generated: number
}

export interface DeviceResponse {
  id: string
  name: string
  device_type: string
  room_id: string | null
  status: string
  properties: Record<string, unknown>
}

export interface SimulationEvent {
  id: string
  event_type: string
  timestamp: string
  source_id: string
  source_type: string
  data: Record<string, unknown>
  is_anomaly: boolean
}

export interface HomeTemplate {
  id: string
  name: string
  rooms: number
  typical_devices: number
  typical_inhabitants: number
  total_area_sqm: number
  floors: number
}

// =============================================================================
// API Service
// =============================================================================

class SimulationApiService {
  private isAvailable = false
  private lastCheck = 0
  private checkInterval = 10000 // 10 seconds

  /**
   * Check if Simulation API is available
   */
  async checkAvailability(): Promise<boolean> {
    const now = Date.now()
    if (now - this.lastCheck < this.checkInterval && this.lastCheck > 0) {
      return this.isAvailable
    }

    try {
      const response = await fetch(`${API_BASE}/templates`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      })
      this.isAvailable = response.ok
    } catch {
      this.isAvailable = false
    }

    this.lastCheck = now
    return this.isAvailable
  }

  // ---------------------------------------------------------------------------
  // Home Management
  // ---------------------------------------------------------------------------

  /**
   * Create a home from template
   */
  async createHome(request: HomeCreateRequest): Promise<HomeResponse> {
    const response = await fetch(`${API_BASE}/home`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to create home: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Create a custom home from Home Builder configuration
   */
  async createCustomHome(request: CustomHomeCreateRequest): Promise<HomeResponse> {
    const response = await fetch(`${API_BASE}/home/custom`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to create custom home: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get current home configuration
   */
  async getHome(): Promise<HomeResponse> {
    const response = await fetch(`${API_BASE}/home`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get home: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get all devices in the current home
   */
  async getDevices(filters?: { room_id?: string; device_type?: string }): Promise<DeviceResponse[]> {
    const params = new URLSearchParams()
    if (filters?.room_id) params.append('room_id', filters.room_id)
    if (filters?.device_type) params.append('device_type', filters.device_type)

    const response = await fetch(`${API_BASE}/home/devices?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get devices: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get home statistics
   */
  async getHomeStats(): Promise<{
    total_devices: number
    total_rooms: number
    total_inhabitants: number
    devices_online: number
    devices_offline: number
    devices_compromised: number
    total_network_traffic_bytes: number
  }> {
    const response = await fetch(`${API_BASE}/home/stats`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get home stats: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Simulation Control
  // ---------------------------------------------------------------------------

  /**
   * Start a simulation
   */
  async start(request: SimulationStartRequest): Promise<SimulationStatusResponse> {
    const response = await fetch(`${API_BASE}/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      let errorMessage = `Failed to start simulation: ${response.statusText}`
      if (error.detail) {
        if (Array.isArray(error.detail)) {
          // Pydantic validation error format
          errorMessage = error.detail.map((e: { msg?: string; loc?: string[] }) =>
            `${e.loc?.join('.') || 'field'}: ${e.msg || 'invalid'}`
          ).join('; ')
        } else {
          errorMessage = String(error.detail)
        }
      }
      throw new Error(errorMessage)
    }

    return response.json()
  }

  /**
   * Get simulation status
   */
  async getStatus(): Promise<SimulationStatusResponse> {
    const response = await fetch(`${API_BASE}/status`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get simulation status: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Pause simulation
   */
  async pause(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE}/pause`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to pause simulation: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Resume simulation
   */
  async resume(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE}/resume`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to resume simulation: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Stop simulation
   */
  async stop(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE}/stop`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to stop simulation: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Event Retrieval
  // ---------------------------------------------------------------------------

  /**
   * Get simulation events
   */
  async getEvents(filters?: {
    event_type?: string
    device_id?: string
    anomalies_only?: boolean
    limit?: number
    offset?: number
  }): Promise<SimulationEvent[]> {
    const params = new URLSearchParams()
    if (filters?.event_type) params.append('event_type', filters.event_type)
    if (filters?.device_id) params.append('device_id', filters.device_id)
    if (filters?.anomalies_only) params.append('anomalies_only', 'true')
    if (filters?.limit) params.append('limit', filters.limit.toString())
    if (filters?.offset) params.append('offset', filters.offset.toString())

    const response = await fetch(`${API_BASE}/events?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get events: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Export all events
   */
  async exportEvents(): Promise<Record<string, unknown>[]> {
    const response = await fetch(`${API_BASE}/events/export`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to export events: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get device telemetry data
   */
  async getDeviceData(deviceId: string): Promise<Record<string, unknown>[]> {
    const response = await fetch(`${API_BASE}/devices/${deviceId}/data`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get device data: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Templates & Metadata
  // ---------------------------------------------------------------------------

  /**
   * Get available home templates
   */
  async getTemplates(): Promise<HomeTemplate[]> {
    const response = await fetch(`${API_BASE}/templates`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get templates: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get available device types
   */
  async getDeviceTypes(): Promise<{ id: string; name: string }[]> {
    const response = await fetch(`${API_BASE}/device-types`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get device types: ${response.statusText}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const simulationApi = new SimulationApiService()

// Export helper to convert frontend home config to backend format
export function convertHomeConfigToBackend(
  config: {
    rooms: Array<{
      id: string
      name: string
      type: string
      x: number
      y: number
      width: number
      height: number
      devices: Array<{
        id: string
        name: string
        type: string
        icon?: string
        x?: number
        y?: number
        status?: string
      }>
    }>
    inhabitants: Array<{
      id: string
      name: string
      role: string
      icon?: string
      currentRoom?: string
    }>
  },
  name = 'Simulation Home'
): CustomHomeCreateRequest {
  return {
    name,
    rooms: config.rooms.map(room => ({
      id: room.id,
      name: room.name,
      type: room.type,
      x: room.x,
      y: room.y,
      width: room.width,
      height: room.height,
      devices: room.devices.map(device => ({
        id: device.id,
        name: device.name,
        type: device.type,
      })),
    })),
    inhabitants: config.inhabitants.map(inhabitant => ({
      id: inhabitant.id,
      name: inhabitant.name,
      role: inhabitant.role,
      age: 30,
      schedule: {
        wakeUp: 7,
        sleep: 23,
        workFromHome: false,
      },
    })),
  }
}