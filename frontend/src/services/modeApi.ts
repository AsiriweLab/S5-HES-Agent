/**
 * Mode API Service
 *
 * Frontend client for the No-LLM Mode / Dual-Mode backend API.
 * Handles expert consultations, pre-loaded scenarios, and mode management.
 */

const API_BASE = 'http://localhost:8000/api/mode'

// =============================================================================
// Types
// =============================================================================

export type InteractionMode = 'llm' | 'no-llm'

export type ConsultationStatus = 'pending' | 'accepted' | 'rejected'

export interface ExpertConsultationRequest {
  question: string
  context?: string
  session_id?: string
  use_rag?: boolean
}

export interface ExpertConsultationResponse {
  id: string
  question: string
  context: string
  response: string
  sources: string[]
  confidence: string
  confidence_score: number
  status: ConsultationStatus
  timestamp: string
  rag_context_count: number
  inference_time_ms: number
  verification_notes: string[]
}

export interface ConsultationFeedback {
  accepted: boolean
  reason?: string
  notes?: string
}

export interface ConsultationFeedbackResponse {
  id: string
  status: ConsultationStatus
  feedback_recorded: boolean
  timestamp: string
}

export interface PreloadedScenario {
  id: string
  name: string
  description: string
  category: string
  difficulty: string
  tags: string[]
  home_config?: Record<string, unknown>
  threat_config?: Record<string, unknown>
  simulation_params?: Record<string, unknown>
}

export interface ScenarioExecutionResponse {
  execution_id: string
  scenario_id: string
  scenario_name: string
  status: string
  home_id?: string
  simulation_id?: string
  results?: Record<string, unknown>
  timestamp: string
}

export interface ModeStatusResponse {
  mode: InteractionMode
  pending_consultations: number
  total_consultations: number
  accepted_consultations: number
  rejected_consultations: number
  available_scenarios: number
  llm_available: boolean
}

export interface ModeStatistics {
  total_consultations: number
  acceptance_rate: number | null
  average_confidence: number | null
  confidence_distribution: Record<string, number>
  consultation_by_status: Record<string, number>
}

// =============================================================================
// API Service Class
// =============================================================================

class ModeApiService {
  private currentMode: InteractionMode = 'llm'

  /**
   * Get the current mode for use in request headers
   */
  getCurrentMode(): InteractionMode {
    return this.currentMode
  }

  /**
   * Set the current mode locally (call setMode() to persist to backend)
   */
  setCurrentModeLocal(mode: InteractionMode): void {
    this.currentMode = mode
  }

  /**
   * Create headers with mode information
   */
  private getHeaders(contentType = true): HeadersInit {
    const headers: HeadersInit = {
      Accept: 'application/json',
      'X-Interaction-Mode': this.currentMode,
    }
    if (contentType) {
      headers['Content-Type'] = 'application/json'
    }
    return headers
  }

  // ---------------------------------------------------------------------------
  // Mode Management
  // ---------------------------------------------------------------------------

  /**
   * Get current mode status
   */
  async getStatus(): Promise<ModeStatusResponse> {
    const response = await fetch(`${API_BASE}/status`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get mode status: ${response.statusText}`)
    }

    const status = await response.json()
    this.currentMode = status.mode
    return status
  }

  /**
   * Set the interaction mode
   */
  async setMode(mode: InteractionMode): Promise<{ status: string; previous_mode: string; current_mode: string }> {
    const response = await fetch(`${API_BASE}/set?mode=${mode}`, {
      method: 'POST',
      headers: this.getHeaders(),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to set mode: ${response.statusText}`)
    }

    const result = await response.json()
    this.currentMode = mode
    return result
  }

  /**
   * Get current mode
   */
  async getCurrentModeFromServer(): Promise<InteractionMode> {
    const response = await fetch(`${API_BASE}/current`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get current mode: ${response.statusText}`)
    }

    const result = await response.json()
    this.currentMode = result.mode
    return result.mode
  }

  // ---------------------------------------------------------------------------
  // Expert Consultations
  // ---------------------------------------------------------------------------

  /**
   * Request expert AI consultation
   */
  async requestConsultation(request: ExpertConsultationRequest): Promise<ExpertConsultationResponse> {
    const response = await fetch(`${API_BASE}/expert-consultation`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to request consultation: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get a specific consultation
   */
  async getConsultation(consultationId: string): Promise<ExpertConsultationResponse> {
    const response = await fetch(`${API_BASE}/expert-consultation/${consultationId}`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get consultation: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * List all consultations
   */
  async listConsultations(
    status?: ConsultationStatus,
    limit = 50,
    offset = 0
  ): Promise<ExpertConsultationResponse[]> {
    const params = new URLSearchParams()
    if (status) params.append('status', status)
    params.append('limit', limit.toString())
    params.append('offset', offset.toString())

    const response = await fetch(`${API_BASE}/expert-consultation?${params.toString()}`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to list consultations: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Submit feedback for a consultation
   */
  async submitFeedback(
    consultationId: string,
    feedback: ConsultationFeedback
  ): Promise<ConsultationFeedbackResponse> {
    const response = await fetch(`${API_BASE}/expert-consultation/${consultationId}/feedback`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(feedback),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to submit feedback: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Pre-loaded Scenarios
  // ---------------------------------------------------------------------------

  /**
   * List all available scenarios
   */
  async listScenarios(
    category?: string,
    difficulty?: string,
    tag?: string
  ): Promise<PreloadedScenario[]> {
    const params = new URLSearchParams()
    if (category) params.append('category', category)
    if (difficulty) params.append('difficulty', difficulty)
    if (tag) params.append('tag', tag)

    const response = await fetch(`${API_BASE}/scenarios?${params.toString()}`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to list scenarios: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get a specific scenario
   */
  async getScenario(scenarioId: string): Promise<PreloadedScenario> {
    const response = await fetch(`${API_BASE}/scenarios/${scenarioId}`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get scenario: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Execute a pre-loaded scenario
   */
  async executeScenario(
    scenarioId: string,
    customParams?: Record<string, unknown>
  ): Promise<ScenarioExecutionResponse> {
    const response = await fetch(`${API_BASE}/scenarios/${scenarioId}/execute`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: customParams ? JSON.stringify({ scenario_id: scenarioId, custom_params: customParams }) : undefined,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Failed to execute scenario: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get all scenario categories
   */
  async getScenarioCategories(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/scenarios/categories`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get categories: ${response.statusText}`)
    }

    const result = await response.json()
    return result.categories
  }

  /**
   * Get all scenario tags
   */
  async getScenarioTags(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/scenarios/tags`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get tags: ${response.statusText}`)
    }

    const result = await response.json()
    return result.tags
  }

  // ---------------------------------------------------------------------------
  // Statistics
  // ---------------------------------------------------------------------------

  /**
   * Get detailed mode statistics
   */
  async getStatistics(): Promise<ModeStatistics> {
    const response = await fetch(`${API_BASE}/statistics`, {
      method: 'GET',
      headers: this.getHeaders(false),
    })

    if (!response.ok) {
      throw new Error(`Failed to get statistics: ${response.statusText}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const modeApi = new ModeApiService()

// Export types for use in components
export type { ModeApiService }
