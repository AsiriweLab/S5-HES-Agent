/**
 * Experiments API Service
 *
 * Frontend client for experiment versioning system.
 * Provides Git-like version control for research experiments.
 */

const API_BASE = 'http://localhost:8000/api/experiments'

// =============================================================================
// Types
// =============================================================================

export interface SemanticVersion {
  major: number
  minor: number
  patch: number
}

export interface RAGSourceReference {
  doc_id: string
  title: string
  source: string
  category: string
  relevance_score: number
  excerpt?: string
  retrieved_at: string
}

export interface ProvenanceMetadata {
  created_by: string
  created_at: string
  modified_by?: string
  modified_at?: string
  research_question?: string
  hypothesis?: string
  methodology_notes?: string
  rag_sources: RAGSourceReference[]
  llm_assisted: boolean
  llm_model?: string
  llm_conversation_id?: string
  verification_passed: boolean
  verification_timestamp?: string
  verification_warnings: string[]
}

export interface ConfigurationSnapshot {
  snapshot_id: string
  created_at: string
  home_config: Record<string, unknown>
  simulation_params: Record<string, unknown>
  threat_scenarios: Record<string, unknown>[]
  behavior_config: Record<string, unknown>
  research_integrity: Record<string, unknown>
  system_info: Record<string, unknown>
}

export interface ExperimentVersion {
  version_id: string
  version: SemanticVersion
  parent_version_id?: string
  branch_name: string
  config_snapshot: ConfigurationSnapshot
  provenance: ProvenanceMetadata
  commit_message: string
  tags: string[]
  notes?: string
  results_path?: string
  metrics_summary: Record<string, unknown>
}

export interface Experiment {
  experiment_id: string
  name: string
  description?: string
  status: 'draft' | 'running' | 'completed' | 'failed' | 'archived'
  versions: ExperimentVersion[]
  current_version_id?: string
  branches: Record<string, string>
  current_branch: string
  created_at: string
  last_modified: string
  tags: string[]
  category?: string
}

export interface ConfigDiff {
  field_path: string
  diff_type: 'added' | 'removed' | 'modified' | 'unchanged'
  old_value?: unknown
  new_value?: unknown
}

export interface VersionComparison {
  version_a_id: string
  version_b_id: string
  differences: ConfigDiff[]
  summary: {
    added: number
    removed: number
    modified: number
  }
}

export interface ExperimentStats {
  total_experiments: number
  total_versions: number
  total_branches: number
  status_breakdown: Record<string, number>
  storage_path: string
}

export interface CurrentStateResponse {
  has_home: boolean
  has_threats: boolean
  home_config: Record<string, unknown>
  simulation_params: Record<string, unknown>
  threat_scenarios: Record<string, unknown>[]
  behavior_config: Record<string, unknown>
  summary: {
    total_rooms: number
    total_devices: number
    total_inhabitants: number
    total_threats: number
  }
}

// Request types
export interface CreateExperimentRequest {
  name: string
  description?: string
  tags?: string[]
  category?: string
  initial_config?: {
    home_config?: Record<string, unknown>
    simulation_params?: Record<string, unknown>
    threat_scenarios?: Record<string, unknown>[]
    behavior_config?: Record<string, unknown>
    research_integrity?: Record<string, unknown>
  }
}

export interface CommitRequest {
  message: string
  version_type?: 'major' | 'minor' | 'patch'
  home_config?: Record<string, unknown>
  simulation_params?: Record<string, unknown>
  threat_scenarios?: Record<string, unknown>[]
  behavior_config?: Record<string, unknown>
  research_integrity?: Record<string, unknown>
  tags?: string[]
  notes?: string
  created_by?: string
  research_question?: string
  hypothesis?: string
  methodology_notes?: string
  llm_assisted?: boolean
  llm_model?: string
  rag_sources?: {
    doc_id: string
    title: string
    source: string
    category: string
    relevance_score: number
    excerpt?: string
  }[]
}

// =============================================================================
// API Service
// =============================================================================

class ExperimentsApiService {
  private isAvailable = false
  private lastCheck = 0
  private checkInterval = 30000

  /**
   * Check if Experiments API is available
   */
  async checkAvailability(): Promise<boolean> {
    const now = Date.now()
    if (now - this.lastCheck < this.checkInterval && this.lastCheck > 0) {
      return this.isAvailable
    }

    try {
      const response = await fetch(`${API_BASE}/stats/overview`, {
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
  // Experiment CRUD
  // ---------------------------------------------------------------------------

  /**
   * List all experiments with optional filters
   */
  async listExperiments(filters?: {
    status?: string
    category?: string
    tags?: string[]
  }): Promise<{ experiments: Experiment[]; total: number }> {
    const params = new URLSearchParams()
    if (filters?.status) params.append('status', filters.status)
    if (filters?.category) params.append('category', filters.category)
    if (filters?.tags) params.append('tags', filters.tags.join(','))

    const response = await fetch(`${API_BASE}/?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to list experiments: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Create a new experiment
   */
  async createExperiment(request: CreateExperimentRequest): Promise<Experiment> {
    const response = await fetch(`${API_BASE}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`Failed to create experiment: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get an experiment by ID
   */
  async getExperiment(experimentId: string): Promise<Experiment> {
    const response = await fetch(`${API_BASE}/${experimentId}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get experiment: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Update experiment metadata
   */
  async updateExperiment(
    experimentId: string,
    updates: {
      name?: string
      description?: string
      status?: string
      tags?: string[]
      category?: string
    }
  ): Promise<Experiment> {
    const response = await fetch(`${API_BASE}/${experimentId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(updates),
    })

    if (!response.ok) {
      throw new Error(`Failed to update experiment: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Delete an experiment
   */
  async deleteExperiment(experimentId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/${experimentId}`, {
      method: 'DELETE',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to delete experiment: ${response.statusText}`)
    }
  }

  // ---------------------------------------------------------------------------
  // Version Control
  // ---------------------------------------------------------------------------

  /**
   * Commit a new version
   */
  async commit(experimentId: string, request: CommitRequest): Promise<ExperimentVersion> {
    const response = await fetch(`${API_BASE}/${experimentId}/commit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`Failed to commit version: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Checkout a specific version or branch
   */
  async checkout(
    experimentId: string,
    options: { version_id?: string; branch?: string }
  ): Promise<ExperimentVersion> {
    const response = await fetch(`${API_BASE}/${experimentId}/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(options),
    })

    if (!response.ok) {
      throw new Error(`Failed to checkout: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get version history
   */
  async getVersionLog(
    experimentId: string,
    options?: { branch?: string; limit?: number }
  ): Promise<{ versions: ExperimentVersion[]; total: number; branch: string }> {
    const params = new URLSearchParams()
    if (options?.branch) params.append('branch', options.branch)
    if (options?.limit) params.append('limit', options.limit.toString())

    const response = await fetch(`${API_BASE}/${experimentId}/log?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get version log: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Branches
  // ---------------------------------------------------------------------------

  /**
   * List branches for an experiment
   */
  async listBranches(
    experimentId: string
  ): Promise<{ branches: Record<string, string>; current_branch: string }> {
    const response = await fetch(`${API_BASE}/${experimentId}/branches`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to list branches: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Create a new branch
   */
  async createBranch(
    experimentId: string,
    branchName: string,
    fromVersionId?: string
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/${experimentId}/branches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        branch_name: branchName,
        from_version_id: fromVersionId,
      }),
    })

    if (!response.ok) {
      throw new Error(`Failed to create branch: ${response.statusText}`)
    }
  }

  // ---------------------------------------------------------------------------
  // Comparison
  // ---------------------------------------------------------------------------

  /**
   * Compare two versions
   */
  async diff(
    experimentId: string,
    versionA: string,
    versionB: string
  ): Promise<VersionComparison> {
    const params = new URLSearchParams()
    params.append('version_a', versionA)
    params.append('version_b', versionB)

    const response = await fetch(`${API_BASE}/${experimentId}/diff?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to diff versions: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Tags and Notes
  // ---------------------------------------------------------------------------

  /**
   * Add a tag to a version
   */
  async addTag(experimentId: string, versionId: string, tag: string): Promise<void> {
    const response = await fetch(`${API_BASE}/${experimentId}/versions/${versionId}/tags`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ tag }),
    })

    if (!response.ok) {
      throw new Error(`Failed to add tag: ${response.statusText}`)
    }
  }

  /**
   * Update notes for a version
   */
  async updateNotes(experimentId: string, versionId: string, notes: string): Promise<void> {
    const response = await fetch(`${API_BASE}/${experimentId}/versions/${versionId}/notes`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ notes }),
    })

    if (!response.ok) {
      throw new Error(`Failed to update notes: ${response.statusText}`)
    }
  }

  // ---------------------------------------------------------------------------
  // Export/Import
  // ---------------------------------------------------------------------------

  /**
   * Export an experiment
   */
  async exportExperiment(
    experimentId: string,
    options?: { export_path?: string; include_results?: boolean }
  ): Promise<{ status: string; experiment_id: string; export_path: string }> {
    const params = new URLSearchParams()
    if (options?.export_path) params.append('export_path', options.export_path)
    if (options?.include_results !== undefined) {
      params.append('include_results', options.include_results.toString())
    }

    const response = await fetch(`${API_BASE}/${experimentId}/export?${params.toString()}`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to export experiment: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Import an experiment
   */
  async importExperiment(importPath: string): Promise<Experiment> {
    const params = new URLSearchParams()
    params.append('import_path', importPath)

    const response = await fetch(`${API_BASE}/import?${params.toString()}`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to import experiment: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Save from Simulation
  // ---------------------------------------------------------------------------

  /**
   * Save a completed simulation run as a new experiment
   */
  async saveFromSimulation(request: {
    name: string
    description?: string
    tags?: string[]
    category?: string
    simulation_id: string
    completed_at: string
    duration_minutes: number
    simulation_mode: string
    home_config: Record<string, unknown>
    threat_scenario?: Record<string, unknown> | null
    statistics: Record<string, unknown>
    event_log: Record<string, unknown>[]
  }): Promise<Experiment> {
    const response = await fetch(`${API_BASE}/from-simulation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Failed to save simulation as experiment: ${errorText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Statistics
  // ---------------------------------------------------------------------------

  /**
   * Get experiment statistics
   */
  async getStats(): Promise<ExperimentStats> {
    const response = await fetch(`${API_BASE}/stats/overview`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get stats: ${response.statusText}`)
    }

    return response.json()
  }

  // ---------------------------------------------------------------------------
  // Current State
  // ---------------------------------------------------------------------------

  /**
   * Get current simulation state for importing into experiments
   */
  async getCurrentState(): Promise<CurrentStateResponse> {
    const response = await fetch(`${API_BASE}/current-state`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Failed to get current state: ${response.statusText}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const experimentsApi = new ExperimentsApiService()

// Helper to format version
export function formatVersion(version: SemanticVersion): string {
  return `v${version.major}.${version.minor}.${version.patch}`
}

// Helper to format date
export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}