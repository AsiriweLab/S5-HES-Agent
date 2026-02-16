<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  agentsApi,
  type AgentStatus,
  type CommunicationLogEntry,
  type TaskQueueItem as ApiTaskQueueItem,
  type PerformanceMetrics as ApiPerformanceMetrics,
} from '@/services/agentsApi'

// Types - Transformed for UI compatibility
interface Agent {
  id: string
  name: string
  type: 'orchestrator' | 'home' | 'behavior' | 'threat' | 'device' | 'rag' | 'output' | 'home_builder' | 'device_manager' | 'threat_injector'
  status: 'idle' | 'working' | 'waiting' | 'error' | 'executing' | 'thinking' | 'completed'
  currentTask: string | null
  lastActivity: Date
  tasksCompleted: number
  avgResponseTime: number
  errorCount: number
}

interface CommunicationLog {
  id: string
  timestamp: Date
  from: string
  to: string
  type: 'request' | 'response' | 'event' | 'error'
  message: string
  payload?: Record<string, unknown>
}

interface TaskQueueItem {
  id: string
  agentId: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  status: 'queued' | 'processing' | 'completed' | 'failed'
  createdAt: Date
  startedAt?: Date
  completedAt?: Date
}

interface PerformanceMetrics {
  llmLatency: number
  ragQueryTime: number
  avgTaskDuration: number
  successRate: number
  throughput: number
}

// State
const agents = ref<Agent[]>([])
const communicationLogs = ref<CommunicationLog[]>([])
const taskQueue = ref<TaskQueueItem[]>([])
const selectedAgent = ref<Agent | null>(null)
const isSimulating = ref(false)
const isApiAvailable = ref(false)
const isLoading = ref(false)

const performanceMetrics = ref<PerformanceMetrics>({
  llmLatency: 0,
  ragQueryTime: 0,
  avgTaskDuration: 0,
  successRate: 100,
  throughput: 0
})

// Simulation cycle step tracker
const simulationCycle = ref(0)

// Polling interval
let pollingInterval: ReturnType<typeof setInterval> | null = null

// Computed
const activeAgents = computed(() => agents.value.filter(a => a.status === 'working' || a.status === 'executing').length)
const totalTasksCompleted = computed(() => agents.value.reduce((sum, a) => sum + a.tasksCompleted, 0))
const totalErrors = computed(() => agents.value.reduce((sum, a) => sum + a.errorCount, 0))
const avgResponseTime = computed(() => {
  if (agents.value.length === 0) return 0
  const total = agents.value.reduce((sum, a) => sum + a.avgResponseTime, 0)
  return Math.round(total / agents.value.length)
})

const filteredLogs = ref<'all' | 'request' | 'response' | 'event' | 'error'>('all')
const displayedLogs = computed(() => {
  if (filteredLogs.value === 'all') return communicationLogs.value.slice(-50)
  return communicationLogs.value.filter(l => l.type === filteredLogs.value).slice(-50)
})

const queuedTasks = computed(() => taskQueue.value.filter(t => t.status === 'queued').length)
const processingTasks = computed(() => taskQueue.value.filter(t => t.status === 'processing').length)

// Transform API data to UI format
function transformAgent(apiAgent: AgentStatus): Agent {
  // Map agent type to UI type
  const typeMap: Record<string, Agent['type']> = {
    'orchestrator': 'orchestrator',
    'home_builder': 'home',
    'device_manager': 'device',
    'threat_injector': 'threat',
    'behavior': 'behavior',
    'rag': 'rag',
    'output': 'output',
  }

  // Map status
  const statusMap: Record<string, Agent['status']> = {
    'idle': 'idle',
    'executing': 'working',
    'thinking': 'working',
    'waiting': 'waiting',
    'error': 'error',
    'completed': 'idle',
  }

  return {
    id: apiAgent.agent_id,
    name: apiAgent.name,
    type: typeMap[apiAgent.type] || apiAgent.type as Agent['type'],
    status: statusMap[apiAgent.status] || 'idle',
    currentTask: apiAgent.current_task,
    lastActivity: new Date(apiAgent.last_activity),
    tasksCompleted: apiAgent.tasks_completed,
    avgResponseTime: Math.round(apiAgent.avg_response_time_ms),
    errorCount: apiAgent.error_count,
  }
}

function transformLog(apiLog: CommunicationLogEntry): CommunicationLog {
  return {
    id: apiLog.id,
    timestamp: new Date(apiLog.timestamp),
    from: apiLog.from,
    to: apiLog.to,
    type: apiLog.type,
    message: apiLog.message,
    payload: apiLog.payload,
  }
}

function transformTask(apiTask: ApiTaskQueueItem): TaskQueueItem {
  return {
    id: apiTask.id,
    agentId: apiTask.agent_id,
    description: apiTask.description,
    priority: apiTask.priority,
    status: apiTask.status,
    createdAt: new Date(apiTask.created_at),
    startedAt: apiTask.started_at ? new Date(apiTask.started_at) : undefined,
    completedAt: apiTask.completed_at ? new Date(apiTask.completed_at) : undefined,
  }
}

function transformPerformance(apiPerf: ApiPerformanceMetrics): PerformanceMetrics {
  return {
    llmLatency: Math.round(apiPerf.llm_latency_ms),
    ragQueryTime: Math.round(apiPerf.rag_query_time_ms),
    avgTaskDuration: Math.round(apiPerf.avg_task_duration_ms),
    successRate: apiPerf.success_rate,
    throughput: apiPerf.throughput,
  }
}

// Methods
function getAgentIcon(type: Agent['type']): string {
  const icons: Record<string, string> = {
    orchestrator: '🎯',
    home: '🏠',
    home_builder: '🏠',
    behavior: '👤',
    threat: '⚠️',
    threat_injector: '⚠️',
    device: '📱',
    device_manager: '📱',
    rag: '📚',
    output: '📊'
  }
  return icons[type] || '🤖'
}

function getStatusColor(status: Agent['status']): string {
  const colors: Record<string, string> = {
    idle: 'var(--text-muted)',
    working: 'var(--color-success)',
    executing: 'var(--color-success)',
    thinking: 'var(--color-success)',
    waiting: 'var(--color-warning)',
    error: 'var(--color-error)',
    completed: 'var(--text-muted)',
  }
  return colors[status] || 'var(--text-muted)'
}

function getPriorityColor(priority: TaskQueueItem['priority']): string {
  const colors: Record<TaskQueueItem['priority'], string> = {
    low: '#22c55e',
    medium: '#eab308',
    high: '#f97316',
    critical: '#dc2626'
  }
  return colors[priority]
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', { hour12: false })
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function selectAgent(agent: Agent) {
  selectedAgent.value = selectedAgent.value?.id === agent.id ? null : agent
}

// API Methods
async function loadSnapshot() {
  try {
    const snapshot = await agentsApi.getSnapshot()

    // Update state from snapshot
    agents.value = snapshot.agents.map(transformAgent)
    communicationLogs.value = snapshot.communication_logs.map(transformLog)
    taskQueue.value = snapshot.task_queue.map(transformTask)
    performanceMetrics.value = transformPerformance(snapshot.performance)
    isSimulating.value = snapshot.is_simulating
    simulationCycle.value = snapshot.simulation_cycle

  } catch (error) {
    console.error('Failed to load snapshot:', error)
  }
}

async function startSimulation() {
  try {
    isLoading.value = true
    await agentsApi.startSimulation()
    isSimulating.value = true
    // Start faster polling during simulation
    startPolling(1000)
  } catch (error) {
    console.error('Failed to start simulation:', error)
  } finally {
    isLoading.value = false
  }
}

async function stopSimulation() {
  try {
    isLoading.value = true
    const result = await agentsApi.stopSimulation()
    isSimulating.value = false
    simulationCycle.value = result.cycles_completed
    // Return to normal polling
    startPolling(2000)
    // Reload to get final state
    await loadSnapshot()
  } catch (error) {
    console.error('Failed to stop simulation:', error)
  } finally {
    isLoading.value = false
  }
}

async function manualTrigger(agentId: string) {
  const agent = agents.value.find(a => a.id === agentId)
  if (!agent || agent.status !== 'idle') return

  try {
    // Optimistically update UI
    agent.status = 'working'
    agent.currentTask = 'Manual trigger task'

    await agentsApi.triggerAgent(agentId, {
      description: 'Manual trigger task',
    })

    // Task started in background - polling will update the state
  } catch (error) {
    console.error('Failed to trigger agent:', error)
    agent.status = 'idle'
    agent.currentTask = null
  }
}

async function cancelAgent(agentId: string) {
  const agent = agents.value.find(a => a.id === agentId)
  if (!agent) return

  try {
    await agentsApi.cancelAgent(agentId)
    // Reload to get updated state
    await loadSnapshot()
  } catch (error) {
    console.error('Failed to cancel agent:', error)
  }
}

async function clearLogs() {
  try {
    await agentsApi.clearLogs()
    communicationLogs.value = []
  } catch (error) {
    console.error('Failed to clear logs:', error)
  }
}

// Polling
function startPolling(interval: number = 2000) {
  stopPolling()
  pollingInterval = setInterval(async () => {
    if (isApiAvailable.value) {
      await loadSnapshot()
    }
  }, interval)
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
}

// Lifecycle
onMounted(async () => {
  // Check API availability
  isLoading.value = true
  try {
    isApiAvailable.value = await agentsApi.checkAvailability()

    if (isApiAvailable.value) {
      // Load initial data
      await loadSnapshot()
      // Start polling
      startPolling(2000)
    } else {
      console.warn('Agents API not available - showing API unavailable message')
      // NO fake agent data - show empty state with API unavailable message
      agents.value = []
    }
  } finally {
    isLoading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="agent-dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <div class="header-title">
        <h1>Agent Dashboard</h1>
        <p>Real-time monitoring of AI agent operations</p>
      </div>
      <div class="header-actions">
        <button
          class="btn"
          :class="isSimulating ? 'btn-error' : 'btn-primary'"
          @click="isSimulating ? stopSimulation() : startSimulation()"
        >
          <svg v-if="!isSimulating" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16"></rect>
            <rect x="14" y="4" width="4" height="16"></rect>
          </svg>
          {{ isSimulating ? 'Stop Simulation' : 'Start Simulation' }}
        </button>
      </div>
    </div>

    <!-- API Unavailable Banner -->
    <div v-if="!isApiAvailable && !isLoading" class="api-unavailable-banner">
      <div class="banner-icon">🤖</div>
      <h3>Agent API Unavailable</h3>
      <p>The Agent Dashboard connects to the backend Agent API to display real-time agent status and operations.</p>
      <p class="banner-note">Please ensure the backend server is running on port 8000. No mock data is displayed.</p>
    </div>

    <!-- Overview Stats (only show if API is available) -->
    <div v-if="isApiAvailable" class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon active">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ activeAgents }}</span>
          <span class="stat-label">Active Agents</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon success">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ totalTasksCompleted }}</span>
          <span class="stat-label">Tasks Completed</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon warning">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ totalErrors }}</span>
          <span class="stat-label">Total Errors</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon info">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ avgResponseTime }}ms</span>
          <span class="stat-label">Avg Response Time</span>
        </div>
      </div>
    </div>

    <div v-if="isApiAvailable" class="dashboard-content">
      <!-- Agent Grid -->
      <section class="agents-section">
        <h2>Agent Status</h2>
        <div class="agents-grid">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="agent-card"
            :class="{ selected: selectedAgent?.id === agent.id, working: agent.status === 'working' }"
            @click="selectAgent(agent)"
          >
            <div class="agent-header">
              <span class="agent-icon">{{ getAgentIcon(agent.type) }}</span>
              <div class="agent-status-indicator" :style="{ backgroundColor: getStatusColor(agent.status) }"></div>
            </div>
            <div class="agent-info">
              <h3>{{ agent.name }}</h3>
              <span class="agent-status" :style="{ color: getStatusColor(agent.status) }">
                {{ agent.status }}
              </span>
            </div>
            <div class="agent-task" v-if="agent.currentTask">
              <span class="task-label">Current Task:</span>
              <span class="task-text">{{ agent.currentTask }}</span>
            </div>
            <div class="agent-stats">
              <div class="mini-stat">
                <span class="mini-value">{{ agent.tasksCompleted }}</span>
                <span class="mini-label">Tasks</span>
              </div>
              <div class="mini-stat">
                <span class="mini-value">{{ agent.avgResponseTime }}ms</span>
                <span class="mini-label">Avg Time</span>
              </div>
              <div class="mini-stat">
                <span class="mini-value" :class="{ error: agent.errorCount > 0 }">{{ agent.errorCount }}</span>
                <span class="mini-label">Errors</span>
              </div>
            </div>
            <!-- Play button - shown when idle -->
            <button
              v-if="agent.status === 'idle'"
              class="manual-trigger-btn"
              @click.stop="manualTrigger(agent.id)"
              title="Manually trigger agent"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
            </button>
            <!-- Stop button - shown when working -->
            <button
              v-else
              class="manual-trigger-btn stop-btn"
              @click.stop="cancelAgent(agent.id)"
              title="Cancel agent task"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="6" y="6" width="12" height="12"></rect>
              </svg>
            </button>
          </div>
        </div>
      </section>

      <!-- Performance Metrics -->
      <section class="metrics-section">
        <h2>Performance Metrics</h2>
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">LLM Latency</span>
            <span class="metric-value">{{ formatDuration(performanceMetrics.llmLatency) }}</span>
            <div class="metric-bar">
              <div class="metric-bar-fill" :style="{ width: Math.min(performanceMetrics.llmLatency / 10, 100) + '%' }"></div>
            </div>
          </div>
          <div class="metric-card">
            <span class="metric-label">RAG Query Time</span>
            <span class="metric-value">{{ formatDuration(performanceMetrics.ragQueryTime) }}</span>
            <div class="metric-bar">
              <div class="metric-bar-fill rag" :style="{ width: Math.min(performanceMetrics.ragQueryTime / 10, 100) + '%' }"></div>
            </div>
          </div>
          <div class="metric-card">
            <span class="metric-label">Success Rate</span>
            <span class="metric-value">{{ performanceMetrics.successRate.toFixed(1) }}%</span>
            <div class="metric-bar">
              <div class="metric-bar-fill success" :style="{ width: performanceMetrics.successRate + '%' }"></div>
            </div>
          </div>
          <div class="metric-card">
            <span class="metric-label">Throughput</span>
            <span class="metric-value">{{ performanceMetrics.throughput }} tasks/min</span>
            <div class="metric-bar">
              <div class="metric-bar-fill throughput" :style="{ width: Math.min(performanceMetrics.throughput * 10, 100) + '%' }"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- Task Queue -->
      <section class="queue-section">
        <div class="section-header">
          <h2>Task Queue</h2>
          <div class="queue-stats">
            <span class="queue-stat queued">{{ queuedTasks }} Queued</span>
            <span class="queue-stat processing">{{ processingTasks }} Processing</span>
          </div>
        </div>
        <div class="task-queue" v-if="taskQueue.length > 0">
          <div
            v-for="task in taskQueue.slice(-10)"
            :key="task.id"
            class="queue-item"
            :class="task.status"
          >
            <div class="queue-priority" :style="{ backgroundColor: getPriorityColor(task.priority) }"></div>
            <div class="queue-content">
              <span class="queue-description">{{ task.description }}</span>
              <span class="queue-agent">{{ task.agentId }}</span>
            </div>
            <span class="queue-status">{{ task.status }}</span>
            <span class="queue-time">{{ formatTime(task.createdAt) }}</span>
          </div>
        </div>
        <div v-else class="empty-queue">
          <p>No tasks in queue. Start simulation to see agent activities.</p>
        </div>
      </section>

      <!-- Communication Log -->
      <section class="logs-section">
        <div class="section-header">
          <h2>Communication Log</h2>
          <div class="log-controls">
            <select
              v-model="filteredLogs"
              class="log-filter"
              aria-label="Filter communication logs by type"
              title="Filter logs"
            >
              <option value="all">All</option>
              <option value="request">Requests</option>
              <option value="response">Responses</option>
              <option value="event">Events</option>
              <option value="error">Errors</option>
            </select>
            <button class="btn btn-ghost btn-sm" @click="clearLogs">Clear</button>
          </div>
        </div>
        <div class="communication-log" v-if="displayedLogs.length > 0">
          <div
            v-for="log in displayedLogs"
            :key="log.id"
            class="log-entry"
            :class="log.type"
          >
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-type" :class="log.type">{{ log.type }}</span>
            <span class="log-route">{{ log.from }} → {{ log.to }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
        <div v-else class="empty-log">
          <p>No communication logs yet.</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.agent-dashboard {
  max-width: 1600px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-xl);
}

.header-title h1 {
  font-size: 1.75rem;
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
}

.header-title p {
  margin: 0;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  gap: var(--spacing-md);
}

/* API Unavailable Banner */
.api-unavailable-banner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl) var(--spacing-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  text-align: center;
  min-height: 300px;
  margin-bottom: var(--spacing-xl);
}

.api-unavailable-banner .banner-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.api-unavailable-banner h3 {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-primary);
  font-size: 1.25rem;
}

.api-unavailable-banner p {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-secondary);
  max-width: 500px;
  line-height: 1.5;
}

.api-unavailable-banner .banner-note {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-style: italic;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.active { background: rgba(99, 102, 241, 0.2); color: #6366f1; }
.stat-icon.success { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.stat-icon.warning { background: rgba(234, 179, 8, 0.2); color: #eab308; }
.stat-icon.info { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* Dashboard Content */
.dashboard-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-xl);
}

section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
}

section h2 {
  font-size: 1.1rem;
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--text-primary);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.section-header h2 {
  margin: 0;
}

/* Agents Grid */
.agents-section {
  grid-column: 1 / -1;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--spacing-md);
}

.agent-card {
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.agent-card:hover {
  border-color: var(--color-primary);
}

.agent-card.selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.agent-card.working {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.agent-icon {
  font-size: 1.5rem;
}

.agent-status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.agent-info h3 {
  font-size: 0.9rem;
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
}

.agent-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.agent-task {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-xs);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
}

.task-label {
  color: var(--text-muted);
  display: block;
}

.task-text {
  color: var(--text-secondary);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-stats {
  display: flex;
  justify-content: space-between;
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.mini-value.error {
  color: var(--color-error);
}

.mini-label {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.manual-trigger-btn {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: var(--color-primary);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.agent-card:hover .manual-trigger-btn {
  opacity: 1;
}

.manual-trigger-btn:disabled {
  background: var(--text-muted);
  cursor: not-allowed;
}

.manual-trigger-btn.stop-btn {
  background: var(--color-error);
  opacity: 1;
}

.manual-trigger-btn.stop-btn:hover {
  background: #b91c1c;
}

/* Metrics Section */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.metric-card {
  background: var(--bg-input);
  padding: var(--spacing-md);
  border-radius: var(--radius-sm);
}

.metric-label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.metric-value {
  display: block;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.metric-bar {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.metric-bar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width var(--transition-normal);
}

.metric-bar-fill.rag { background: #8b5cf6; }
.metric-bar-fill.success { background: #22c55e; }
.metric-bar-fill.throughput { background: #3b82f6; }

/* Task Queue */
.queue-stats {
  display: flex;
  gap: var(--spacing-md);
}

.queue-stat {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.queue-stat.queued { background: rgba(234, 179, 8, 0.2); color: #eab308; }
.queue-stat.processing { background: rgba(99, 102, 241, 0.2); color: #6366f1; }

.task-queue {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 300px;
  overflow-y: auto;
}

.queue-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.queue-item.completed { opacity: 0.5; }
.queue-item.failed { border-left: 3px solid var(--color-error); }

.queue-priority {
  width: 4px;
  height: 100%;
  min-height: 32px;
  border-radius: 2px;
}

.queue-content {
  flex: 1;
  min-width: 0;
}

.queue-description {
  display: block;
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.queue-agent {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.queue-status {
  font-size: 0.7rem;
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-transform: capitalize;
}

.queue-time {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: monospace;
}

.empty-queue {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

/* Communication Log */
.log-controls {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.log-filter {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  color: var(--text-primary);
  font-size: 0.8rem;
}

.communication-log {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Fira Code', monospace;
  font-size: 0.75rem;
}

.log-entry {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  align-items: center;
}

.log-entry.error {
  background: rgba(220, 38, 38, 0.1);
}

.log-time {
  color: var(--text-muted);
  min-width: 70px;
}

.log-type {
  font-size: 0.65rem;
  padding: 1px 4px;
  border-radius: 2px;
  text-transform: uppercase;
  font-weight: 600;
  min-width: 60px;
  text-align: center;
}

.log-type.request { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.log-type.response { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.log-type.event { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
.log-type.error { background: rgba(220, 38, 38, 0.2); color: #dc2626; }

.log-route {
  color: var(--text-secondary);
  min-width: 150px;
}

.log-message {
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-log {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-header {
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .agents-grid {
    grid-template-columns: 1fr;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
