/**
 * LLM Provider API Service
 *
 * Client for the backend LLM Provider API.
 * Enables runtime LLM provider selection and model switching.
 */

const API_BASE = 'http://localhost:8000/api/llm'

// =============================================================================
// Types
// =============================================================================

export interface ProviderInfo {
  name: string
  display_name: string
  is_configured: boolean
  is_active: boolean
  requires_api_key: boolean
  api_key_env_var: string | null
  default_model: string
  available_models: string[]
  status_message: string
}

export interface ProvidersResponse {
  providers: ProviderInfo[]
  active_provider: string | null
  active_model: string | null
}

export interface SwitchProviderRequest {
  provider: string
  model?: string
}

export interface SwitchProviderResponse {
  success: boolean
  provider: string
  model: string
  message: string
  persisted: boolean
}

export interface ModelsResponse {
  provider: string
  models: string[]
  default_model: string
}

export interface ConfigVariable {
  name: string
  description: string
  current: string
  options?: string[]
}

export interface ConfigFile {
  path: string
  description: string
  variables?: ConfigVariable[]
}

export interface ConfigInfoResponse {
  message: string
  files: ConfigFile[]
  note: string
}

// =============================================================================
// API Client
// =============================================================================

class LLMApiService {
  /**
   * Get all available LLM providers with their status
   */
  async getProviders(): Promise<ProvidersResponse> {
    const response = await fetch(`${API_BASE}/providers`)
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch providers' }))
      throw new Error(error.detail || 'Failed to fetch providers')
    }
    return response.json()
  }

  /**
   * Switch to a different LLM provider
   */
  async switchProvider(provider: string, model?: string): Promise<SwitchProviderResponse> {
    const response = await fetch(`${API_BASE}/switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model }),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to switch provider' }))
      throw new Error(error.detail?.message || error.detail || 'Failed to switch provider')
    }
    return response.json()
  }

  /**
   * Get available models for a specific provider
   */
  async getModels(provider: string): Promise<ModelsResponse> {
    const response = await fetch(`${API_BASE}/models/${provider}`)
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch models' }))
      throw new Error(error.detail || 'Failed to fetch models')
    }
    return response.json()
  }

  /**
   * Get configuration info for persisting provider changes
   */
  async getConfigInfo(): Promise<ConfigInfoResponse> {
    const response = await fetch(`${API_BASE}/config-info`)
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch config info' }))
      throw new Error(error.detail || 'Failed to fetch config info')
    }
    return response.json()
  }
}

// Export singleton instance
export const llmApi = new LLMApiService()
