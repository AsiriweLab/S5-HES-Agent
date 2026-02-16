/**
 * Parameter Sweep & Statistics API Service
 *
 * Client for the backend Parameter Sweep and Statistical Testing API
 * for research workflow automation.
 */

const API_BASE = 'http://localhost:8000/api/sweeps'

// =============================================================================
// Types
// =============================================================================

export type ParameterType = 'discrete' | 'range' | 'linspace' | 'logspace'
export type SweepStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

export interface ParameterDefinition {
  name: string
  param_type: ParameterType
  values: (string | number)[]
  start?: number
  end?: number
  steps?: number
  description?: string
  unit?: string
}

export interface CreateSweepRequest {
  name: string
  description?: string
  base_config: Record<string, unknown>
  parameters: ParameterDefinition[]
  parallel_workers?: number
  repetitions?: number
  random_seed?: number
  tags?: string[]
}

export interface SweepSummary {
  sweep_id: string
  name: string
  status: SweepStatus
  total_experiments: number
  completed_experiments: number
  created_at: string
}

export interface SweepProgress {
  sweep_id: string
  status: SweepStatus
  total_experiments: number
  completed_experiments: number
  failed_experiments: number
  running_experiments: number
  pending_experiments: number
  progress_percent: number
  estimated_remaining_seconds?: number
  start_time?: string
  current_time: string
}

export interface ExperimentResult {
  experiment_id: string
  sweep_id: string
  parameter_values: Record<string, unknown>
  repetition: number
  status: SweepStatus
  start_time?: string
  end_time?: string
  duration_seconds?: number
  metrics: Record<string, number>
  events_count: number
  threats_detected: number
  threats_blocked: number
  error_message?: string
}

export interface SweepResults {
  sweep_id: string
  configuration: CreateSweepRequest & { sweep_id: string; created_at: string }
  status: SweepStatus
  experiments: ExperimentResult[]
  start_time?: string
  end_time?: string
  total_duration_seconds?: number
  summary_statistics: Record<string, Record<string, number>>
  parameter_effects: Record<string, unknown>
}

// Statistical Testing Types
export interface TestResult {
  test_type: string
  test_statistic: number
  p_value: number
  degrees_of_freedom?: number
  effect_size?: number
  effect_size_type?: string
  confidence_interval?: [number, number]
  confidence_level: number
  is_significant: boolean
  alpha: number
  interpretation: string
  sample_sizes: number[]
  group_means: number[]
  group_stds?: number[]
}

export interface DescriptiveStats {
  n: number
  mean: number
  median: number
  std_dev: number
  variance: number
  std_error: number
  min_val: number
  max_val: number
  range_val: number
  q1: number
  q3: number
  iqr: number
  skewness?: number
  kurtosis?: number
}

export interface MultipleComparisonResult {
  original_p_values: number[]
  corrected_p_values: number[]
  correction_method: string
  significant_indices: number[]
  alpha: number
}

export interface PowerAnalysisResult {
  effect_size: number
  alpha: number
  power: number
  sample_size_per_group: number
  total_sample_size: number
}

// =============================================================================
// API Client
// =============================================================================

class SweepsApiService {
  // --------------------------------------------------------------------------
  // Parameter Sweep Endpoints
  // --------------------------------------------------------------------------

  /**
   * Create a new parameter sweep
   */
  async createSweep(request: CreateSweepRequest): Promise<{ sweep_id: string; status: string; total_experiments: number }> {
    const response = await fetch(`${API_BASE}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) throw new Error(`Failed to create sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * List all parameter sweeps
   */
  async listSweeps(status?: SweepStatus): Promise<{ sweeps: SweepSummary[]; total: number }> {
    const url = status ? `${API_BASE}/?status=${status}` : `${API_BASE}/`
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Failed to list sweeps: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get a specific sweep by ID
   */
  async getSweep(sweepId: string): Promise<SweepResults> {
    const response = await fetch(`${API_BASE}/${sweepId}`)
    if (!response.ok) throw new Error(`Failed to get sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * Get sweep progress
   */
  async getSweepProgress(sweepId: string): Promise<SweepProgress> {
    const response = await fetch(`${API_BASE}/${sweepId}/progress`)
    if (!response.ok) throw new Error(`Failed to get progress: ${response.statusText}`)
    return response.json()
  }

  /**
   * Start a sweep
   */
  async startSweep(sweepId: string): Promise<{ sweep_id: string; status: string; message: string }> {
    const response = await fetch(`${API_BASE}/${sweepId}/start`, { method: 'POST' })
    if (!response.ok) throw new Error(`Failed to start sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * Pause a sweep
   */
  async pauseSweep(sweepId: string): Promise<{ sweep_id: string; status: string }> {
    const response = await fetch(`${API_BASE}/${sweepId}/pause`, { method: 'POST' })
    if (!response.ok) throw new Error(`Failed to pause sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * Cancel a sweep
   */
  async cancelSweep(sweepId: string): Promise<{ sweep_id: string; status: string }> {
    const response = await fetch(`${API_BASE}/${sweepId}/cancel`, { method: 'POST' })
    if (!response.ok) throw new Error(`Failed to cancel sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * Delete a sweep
   */
  async deleteSweep(sweepId: string): Promise<{ status: string; sweep_id: string }> {
    const response = await fetch(`${API_BASE}/${sweepId}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Failed to delete sweep: ${response.statusText}`)
    return response.json()
  }

  /**
   * Export sweep results
   */
  async exportSweep(sweepId: string, format: 'json' | 'csv' = 'json'): Promise<{ sweep_id: string; format: string; data: string }> {
    const response = await fetch(`${API_BASE}/${sweepId}/export?format=${format}`)
    if (!response.ok) throw new Error(`Failed to export sweep: ${response.statusText}`)
    return response.json()
  }

  // --------------------------------------------------------------------------
  // Statistical Testing Endpoints
  // --------------------------------------------------------------------------

  /**
   * Calculate descriptive statistics
   */
  async descriptiveStats(data: number[]): Promise<DescriptiveStats> {
    const response = await fetch(`${API_BASE}/stats/descriptive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data }),
    })
    if (!response.ok) throw new Error(`Failed to calculate stats: ${response.statusText}`)
    return response.json()
  }

  /**
   * Perform t-test
   */
  async tTest(
    group1: number[],
    group2: number[],
    options: { alpha?: number; equal_variance?: boolean; paired?: boolean } = {}
  ): Promise<TestResult> {
    const response = await fetch(`${API_BASE}/stats/t-test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        group1,
        group2,
        alpha: options.alpha ?? 0.05,
        equal_variance: options.equal_variance ?? true,
        paired: options.paired ?? false,
      }),
    })
    if (!response.ok) throw new Error(`Failed to perform t-test: ${response.statusText}`)
    return response.json()
  }

  /**
   * Perform ANOVA
   */
  async anova(groups: number[][], alpha: number = 0.05): Promise<TestResult> {
    const response = await fetch(`${API_BASE}/stats/anova`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups, alpha }),
    })
    if (!response.ok) throw new Error(`Failed to perform ANOVA: ${response.statusText}`)
    return response.json()
  }

  /**
   * Perform Mann-Whitney U test
   */
  async mannWhitney(group1: number[], group2: number[], alpha: number = 0.05): Promise<TestResult> {
    const response = await fetch(`${API_BASE}/stats/mann-whitney`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group1, group2, alpha }),
    })
    if (!response.ok) throw new Error(`Failed to perform Mann-Whitney: ${response.statusText}`)
    return response.json()
  }

  /**
   * Perform Kruskal-Wallis H test
   */
  async kruskalWallis(groups: number[][], alpha: number = 0.05): Promise<TestResult> {
    const response = await fetch(`${API_BASE}/stats/kruskal-wallis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups, alpha }),
    })
    if (!response.ok) throw new Error(`Failed to perform Kruskal-Wallis: ${response.statusText}`)
    return response.json()
  }

  /**
   * Calculate correlation
   */
  async correlation(x: number[], y: number[], options: { alpha?: number; method?: 'pearson' | 'spearman' } = {}): Promise<TestResult> {
    const response = await fetch(`${API_BASE}/stats/correlation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        x,
        y,
        alpha: options.alpha ?? 0.05,
        method: options.method ?? 'pearson',
      }),
    })
    if (!response.ok) throw new Error(`Failed to calculate correlation: ${response.statusText}`)
    return response.json()
  }

  /**
   * Calculate effect sizes
   */
  async effectSize(group1: number[], group2: number[]): Promise<{ cohens_d: number; hedges_g: number; interpretation: string }> {
    const response = await fetch(`${API_BASE}/stats/effect-size`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group1, group2 }),
    })
    if (!response.ok) throw new Error(`Failed to calculate effect size: ${response.statusText}`)
    return response.json()
  }

  /**
   * Calculate confidence interval for mean
   */
  async confidenceInterval(data: number[], confidence: number = 0.95): Promise<{ mean: number; confidence_level: number; lower_bound: number; upper_bound: number; margin_of_error: number }> {
    const response = await fetch(`${API_BASE}/stats/confidence-interval?confidence=${confidence}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data }),
    })
    if (!response.ok) throw new Error(`Failed to calculate CI: ${response.statusText}`)
    return response.json()
  }

  /**
   * Apply multiple comparison correction
   */
  async multipleComparison(
    pValues: number[],
    options: { alpha?: number; method?: 'bonferroni' | 'holm' | 'fdr' } = {}
  ): Promise<MultipleComparisonResult> {
    const response = await fetch(`${API_BASE}/stats/multiple-comparison`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        p_values: pValues,
        alpha: options.alpha ?? 0.05,
        method: options.method ?? 'bonferroni',
      }),
    })
    if (!response.ok) throw new Error(`Failed to apply correction: ${response.statusText}`)
    return response.json()
  }

  /**
   * Perform power analysis
   */
  async powerAnalysis(effectSize: number, alpha: number = 0.05, power: number = 0.80): Promise<PowerAnalysisResult> {
    const response = await fetch(`${API_BASE}/stats/power-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ effect_size: effectSize, alpha, power }),
    })
    if (!response.ok) throw new Error(`Failed to perform power analysis: ${response.statusText}`)
    return response.json()
  }
}

// Export singleton instance
export const sweepsApi = new SweepsApiService()
