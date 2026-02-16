/**
 * History API Service
 *
 * Client for the backend History API to retrieve saved simulation data,
 * events, and analytics for the History page.
 */

const API_BASE = 'http://localhost:8000/api/history'

// =============================================================================
// Types
// =============================================================================

export interface HistoricalEvent {
  id: string
  timestamp: string
  category: 'simulation' | 'security' | 'device' | 'network' | 'user'
  type: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  source: string
  message: string
  details: Record<string, unknown>
  tags: string[]
  simulation_id?: string
}

export interface SimulationRun {
  id: string
  name: string
  start_time: string
  end_time?: string
  duration_minutes: number
  status: 'completed' | 'failed' | 'aborted'
  total_events: number
  threats_detected: number
  threats_blocked: number
  compromised_devices: number
  home_config: string
  threat_scenario?: string
  category?: string
  tags: string[]
}

export interface TimelinePoint {
  timestamp: string
  value: number
  category: string
}

export interface HistoryEventsResponse {
  events: HistoricalEvent[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SimulationRunsResponse {
  simulations: SimulationRun[]
  total: number
}

export interface AnalyticsResponse {
  category_stats: Record<string, number>
  severity_stats: Record<string, number>
  timeline_data: TimelinePoint[]
  summary: {
    total_events: number
    total_simulations: number
    avg_events_per_day: number
    most_common_category?: string
    most_common_severity?: string
  }
}

export interface HistoryStatsResponse {
  total_events: number
  total_simulations: number
  completed_simulations: number
  failed_simulations: number
  avg_events_per_simulation: number
  total_threats_detected: number
  total_threats_blocked: number
}

export interface EventsQueryParams {
  page?: number
  page_size?: number
  category?: string
  severity?: string
  search?: string
  start_date?: string
  end_date?: string
}

// =============================================================================
// API Client
// =============================================================================

class HistoryApiService {
  /**
   * Check if the history API is available
   */
  async checkAvailability(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/stats`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Get historical events with optional filters
   */
  async getEvents(params: EventsQueryParams = {}): Promise<HistoryEventsResponse> {
    const searchParams = new URLSearchParams()

    if (params.page) searchParams.set('page', params.page.toString())
    if (params.page_size) searchParams.set('page_size', params.page_size.toString())
    if (params.category) searchParams.set('category', params.category)
    if (params.severity) searchParams.set('severity', params.severity)
    if (params.search) searchParams.set('search', params.search)
    if (params.start_date) searchParams.set('start_date', params.start_date)
    if (params.end_date) searchParams.set('end_date', params.end_date)

    const url = `${API_BASE}/events?${searchParams.toString()}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch events: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get all simulation runs
   */
  async getSimulations(status?: string, limit?: number): Promise<SimulationRunsResponse> {
    const searchParams = new URLSearchParams()

    if (status) searchParams.set('status', status)
    if (limit) searchParams.set('limit', limit.toString())

    const url = `${API_BASE}/simulations?${searchParams.toString()}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch simulations: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get analytics data
   */
  async getAnalytics(days: number = 7): Promise<AnalyticsResponse> {
    const url = `${API_BASE}/analytics?days=${days}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch analytics: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get overall history statistics
   */
  async getStats(): Promise<HistoryStatsResponse> {
    const response = await fetch(`${API_BASE}/stats`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get a specific simulation by ID
   */
  async getSimulation(simulationId: string): Promise<SimulationRun> {
    const response = await fetch(`${API_BASE}/simulation/${simulationId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch simulation: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get events for a specific simulation
   */
  async getSimulationEvents(
    simulationId: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<HistoryEventsResponse> {
    const url = `${API_BASE}/simulation/${simulationId}/events?page=${page}&page_size=${pageSize}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch simulation events: ${response.statusText}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const historyApi = new HistoryApiService()