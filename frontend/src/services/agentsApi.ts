/**
 * Agents API Service
 *
 * Client for the backend Agents API for monitoring and controlling
 * the AI agent system.
 */

const API_BASE = 'http://localhost:8000/api/agents'

// =============================================================================
// Types
// =============================================================================

export interface AgentStatus {
  agent_id: string
  name: string
  type: string
  status: 'idle' | 'thinking' | 'executing' | 'waiting' | 'error' | 'completed'
  current_task: string | null
  last_activity: string
  tasks_completed: number
  tasks_failed: number
  avg_response_time_ms: number
  error_count: number
  pending_messages: number
  capabilities: string[]
}

export interface CommunicationLogEntry {
  id: string
  timestamp: string
  from: string
  to: string
  type: 'request' | 'response' | 'event' | 'error'
  message: string
  payload?: Record<string, unknown>
}

export interface TaskQueueItem {
  id: string
  agent_id: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  status: 'queued' | 'processing' | 'completed' | 'failed'
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface PerformanceMetrics {
  llm_latency_ms: number
  rag_query_time_ms: number
  avg_task_duration_ms: number
  success_rate: number
  throughput: number
  total_tasks_executed: number
  total_messages_exchanged: number
}

export interface OrchestratorStatus {
  state: string
  registered_agents: number
  agents_by_type: Record<string, number>
  active_contexts: number
  stats: Record<string, unknown>
}

export interface AgentDashboardSnapshot {
  orchestrator: OrchestratorStatus
  agents: AgentStatus[]
  communication_logs: CommunicationLogEntry[]
  task_queue: TaskQueueItem[]
  performance: PerformanceMetrics
  is_simulating: boolean
  simulation_cycle: number
}

export interface ManualTriggerRequest {
  task_type?: string
  description?: string
  parameters?: Record<string, unknown>
}

export interface ManualTriggerResponse {
  success: boolean
  task_id: string
  agent_id: string
  message: string
  result?: Record<string, unknown>
  error?: string
}

export interface SimulationStatus {
  is_simulating: boolean
  simulation_cycle: number
}

// =============================================================================
// RL Training Types
// =============================================================================

export interface TrainingConfigRequest {
  n_episodes?: number
  max_steps_per_episode?: number
  learning_rate?: number
  discount_factor?: number
  initial_epsilon?: number
  target_detection_rate?: number
  max_fp_rate?: number
}

export interface TrainingStatusResponse {
  session_id: string | null
  status: 'idle' | 'training' | 'completed' | 'failed'
  current_episode: number
  total_episodes: number
  mean_reward: number
  best_reward: number
  current_detection_rate: number
  current_epsilon: number
  elapsed_time_s: number
}

export interface TrainingSession {
  session_id: string
  status: string
  start_time: string
  end_time?: string
  config: TrainingConfigRequest
  metrics: {
    episode_rewards: number[]
    mean_reward: number
    best_reward: number
    detection_rates: number[]
    false_positive_rates: number[]
    epsilon_values: number[]
  }
}

export interface TrainingHistory {
  sessions: TrainingSession[]
  total_sessions: number
  best_session_id?: string
}

export interface EvaluationResult {
  evaluation_results: {
    mean_reward: number
    std_reward: number
    detection_rate: number
    false_positive_rate: number
    episodes_evaluated: number
  }
  agent_id: string
}

// =============================================================================
// API Client
// =============================================================================

class AgentsApiService {
  /**
   * Check if the agents API is available
   */
  async checkAvailability(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/status`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Get complete dashboard snapshot
   */
  async getSnapshot(): Promise<AgentDashboardSnapshot> {
    const response = await fetch(`${API_BASE}/snapshot`)
    if (!response.ok) {
      throw new Error('Failed to get dashboard snapshot')
    }
    return response.json()
  }

  /**
   * Get orchestrator status
   */
  async getOrchestratorStatus(): Promise<OrchestratorStatus> {
    const response = await fetch(`${API_BASE}/status`)
    if (!response.ok) {
      throw new Error('Failed to get orchestrator status')
    }
    return response.json()
  }

  /**
   * Get all agents
   */
  async getAllAgents(): Promise<AgentStatus[]> {
    const response = await fetch(`${API_BASE}/agents`)
    if (!response.ok) {
      throw new Error('Failed to get agents')
    }
    return response.json()
  }

  /**
   * Get a specific agent
   */
  async getAgent(agentId: string): Promise<AgentStatus> {
    const response = await fetch(`${API_BASE}/agents/${agentId}`)
    if (!response.ok) {
      throw new Error(`Failed to get agent ${agentId}`)
    }
    return response.json()
  }

  /**
   * Manually trigger an agent task
   */
  async triggerAgent(
    agentId: string,
    request: ManualTriggerRequest = {}
  ): Promise<ManualTriggerResponse> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to trigger agent' }))
      throw new Error(error.detail || 'Failed to trigger agent')
    }
    return response.json()
  }

  /**
   * Cancel a running agent task
   */
  async cancelAgent(agentId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/cancel`, {
      method: 'POST',
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to cancel agent' }))
      throw new Error(error.detail || 'Failed to cancel agent')
    }
    return response.json()
  }

  /**
   * Get communication logs
   */
  async getLogs(options: { limit?: number; type?: string } = {}): Promise<CommunicationLogEntry[]> {
    const params = new URLSearchParams()
    if (options.limit) params.set('limit', String(options.limit))
    if (options.type && options.type !== 'all') params.set('type', options.type)

    const url = params.toString() ? `${API_BASE}/logs?${params}` : `${API_BASE}/logs`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error('Failed to get logs')
    }
    return response.json()
  }

  /**
   * Clear communication logs
   */
  async clearLogs(): Promise<void> {
    const response = await fetch(`${API_BASE}/logs`, { method: 'DELETE' })
    if (!response.ok) {
      throw new Error('Failed to clear logs')
    }
  }

  /**
   * Get task queue
   */
  async getTaskQueue(limit: number = 20): Promise<TaskQueueItem[]> {
    const response = await fetch(`${API_BASE}/tasks?limit=${limit}`)
    if (!response.ok) {
      throw new Error('Failed to get task queue')
    }
    return response.json()
  }

  /**
   * Get performance metrics
   */
  async getPerformanceMetrics(): Promise<PerformanceMetrics> {
    const response = await fetch(`${API_BASE}/performance`)
    if (!response.ok) {
      throw new Error('Failed to get performance metrics')
    }
    return response.json()
  }

  /**
   * Start simulation
   */
  async startSimulation(): Promise<SimulationStatus> {
    const response = await fetch(`${API_BASE}/simulation/start`, { method: 'POST' })
    if (!response.ok) {
      throw new Error('Failed to start simulation')
    }
    return response.json()
  }

  /**
   * Stop simulation
   */
  async stopSimulation(): Promise<SimulationStatus & { cycles_completed: number }> {
    const response = await fetch(`${API_BASE}/simulation/stop`, { method: 'POST' })
    if (!response.ok) {
      throw new Error('Failed to stop simulation')
    }
    return response.json()
  }

  /**
   * Get simulation status
   */
  async getSimulationStatus(): Promise<SimulationStatus> {
    const response = await fetch(`${API_BASE}/simulation/status`)
    if (!response.ok) {
      throw new Error('Failed to get simulation status')
    }
    return response.json()
  }

  // ===========================================================================
  // RL Training Methods
  // ===========================================================================

  /**
   * Start RL training for the optimization agent
   */
  async startTraining(config?: TrainingConfigRequest): Promise<{ message: string; config: TrainingConfigRequest }> {
    const response = await fetch(`${API_BASE}/training/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config ?? {}),
    })
    if (!response.ok) {
      throw new Error('Failed to start training')
    }
    return response.json()
  }

  /**
   * Get current training status
   */
  async getTrainingStatus(): Promise<TrainingStatusResponse> {
    const response = await fetch(`${API_BASE}/training/status`)
    if (!response.ok) {
      throw new Error('Failed to get training status')
    }
    return response.json()
  }

  /**
   * Get training history
   */
  async getTrainingHistory(): Promise<TrainingHistory> {
    const response = await fetch(`${API_BASE}/training/history`)
    if (!response.ok) {
      throw new Error('Failed to get training history')
    }
    return response.json()
  }

  /**
   * Evaluate the trained optimization agent
   */
  async evaluateAgent(nEpisodes: number = 10): Promise<EvaluationResult> {
    const response = await fetch(`${API_BASE}/training/evaluate?n_episodes=${nEpisodes}`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new Error('Failed to evaluate agent')
    }
    return response.json()
  }
}

// Export singleton instance
export const agentsApi = new AgentsApiService()
