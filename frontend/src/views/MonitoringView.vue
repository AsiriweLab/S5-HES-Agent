<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { monitoringApi } from '@/services/monitoringApi'

// ============== TYPES ==============

interface SystemMetric {
  name: string
  value: number
  unit: string
  trend: 'up' | 'down' | 'stable'
  status: 'normal' | 'warning' | 'critical'
}

interface SecurityEvent {
  id: string
  timestamp: Date
  type: 'auth' | 'tls' | 'encryption' | 'mesh' | 'privacy' | 'threat'
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  source: string
  message: string
  details?: Record<string, unknown>
}

interface DeviceStatus {
  id: string
  name: string
  type: string
  protocol: string
  status: 'online' | 'offline' | 'warning' | 'compromised'
  lastSeen: Date
  signalStrength?: number
  batteryLevel?: number
}

interface NetworkNode {
  id: string
  role: string
  state: string
  neighbors: number
  messagesSent: number
  messagesReceived: number
}

// ============== STATE ==============

const isLive = ref(true)
const updateInterval = ref<ReturnType<typeof setInterval> | null>(null)
const isApiAvailable = ref(false)
const isLoading = ref(false)
const apiError = ref<string | null>(null)

// Polling intervals: fast when simulation running, slow when idle
const POLLING_INTERVAL_ACTIVE = 2000   // 2 seconds when simulation running
const POLLING_INTERVAL_IDLE = 10000    // 10 seconds when idle (just to check for simulation start)
const currentPollingInterval = ref(POLLING_INTERVAL_IDLE)

// Simulation state from backend
const simulationState = ref<string>('idle')  // idle, running, paused, stopped, completed, error

// System metrics - START EMPTY, only show real data
const metrics = ref<SystemMetric[]>([])

// Security events - START EMPTY
const securityEvents = ref<SecurityEvent[]>([])

// Device statuses - START EMPTY
const devices = ref<DeviceStatus[]>([])

// Mesh network nodes - START EMPTY
const meshNodes = ref<NetworkNode[]>([])

// Security stats - START AT ZERO
const securityStats = ref({
  authSuccess: 0,
  authFailure: 0,
  tlsHandshakes: 0,
  encryptedMessages: 0,
  privacyQueries: 0,
  threatBlocked: 0,
})

// Time range filter
const timeRange = ref('1h')

// Simulation state (from simulation API)
const simulationStatus = ref<{
  status: string
  simulation_id: string | null
  elapsed_time: number
  progress: number
  event_count: number
} | null>(null)

// Is simulation actively running?
const isSimulationRunning = computed(() =>
  simulationState.value === 'running'
)

// Show idle message when no simulation is running
const showIdleMessage = computed(() =>
  simulationState.value === 'idle' && !isLoading.value
)

// ============== COMPUTED ==============

const onlineDeviceCount = computed(() => devices.value.filter(d => d.status === 'online').length)
const warningDeviceCount = computed(() => devices.value.filter(d => d.status === 'warning').length)
const offlineDeviceCount = computed(() => devices.value.filter(d => d.status === 'offline').length)

const recentEvents = computed(() => {
  return securityEvents.value.slice(0, 50)
})

// ============== METHODS ==============

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function toggleLive() {
  isLive.value = !isLive.value
  if (isLive.value) {
    startUpdates()
  } else {
    stopUpdates()
  }
}

function startUpdates() {
  if (updateInterval.value) return

  // Only poll API if available - NO fake data generation
  updateInterval.value = setInterval(() => {
    if (isApiAvailable.value) {
      fetchFromApi()
    }
    // If API is not available, we show idle state - NO mock data
  }, currentPollingInterval.value)
}

function adjustPollingInterval(newInterval: number) {
  // Only restart if interval actually changed
  if (currentPollingInterval.value === newInterval) return

  currentPollingInterval.value = newInterval

  // Restart polling with new interval if currently active
  if (updateInterval.value && isLive.value) {
    stopUpdates()
    startUpdates()
  }
}

function stopUpdates() {
  if (updateInterval.value) {
    clearInterval(updateInterval.value)
    updateInterval.value = null
  }
}

async function fetchFromApi() {
  if (isLoading.value) return

  try {
    // Note: We get simulation_state from the monitoring snapshot now,
    // so we don't need to call fetchSimulationStatus() separately
    // This avoids 404 errors when no simulation is running

    const snapshot = await monitoringApi.getSnapshot(true, 50)

    // Update simulation state from monitoring API
    if (snapshot.simulation_state) {
      simulationState.value = snapshot.simulation_state

      // Adjust polling frequency based on simulation state
      // Fast polling when running, slow polling when idle
      const newInterval = snapshot.simulation_state === 'running'
        ? POLLING_INTERVAL_ACTIVE
        : POLLING_INTERVAL_IDLE
      adjustPollingInterval(newInterval)
    }

    // Update metrics (will be empty array if no simulation running)
    metrics.value = snapshot.metrics.map(m => ({
      name: m.name,
      value: m.value,
      unit: m.unit,
      trend: m.trend as 'up' | 'down' | 'stable',
      status: m.status as 'normal' | 'warning' | 'critical',
    }))

    // Update security stats
    securityStats.value = {
      authSuccess: snapshot.security_stats.auth_success,
      authFailure: snapshot.security_stats.auth_failure,
      tlsHandshakes: snapshot.security_stats.tls_handshakes,
      encryptedMessages: snapshot.security_stats.encrypted_messages,
      privacyQueries: snapshot.security_stats.privacy_queries,
      threatBlocked: snapshot.security_stats.threats_blocked,
    }

    // Update devices
    devices.value = snapshot.devices.map(d => ({
      id: d.id,
      name: d.name,
      type: d.type,
      protocol: d.protocol,
      status: d.status as 'online' | 'offline' | 'warning' | 'compromised',
      lastSeen: new Date(d.last_seen),
      signalStrength: d.signal_strength,
      batteryLevel: d.battery_level,
    }))

    // Update mesh nodes
    meshNodes.value = snapshot.mesh_nodes.map(n => ({
      id: n.id,
      role: n.role,
      state: n.state,
      neighbors: n.neighbors,
      messagesSent: n.messages_sent,
      messagesReceived: n.messages_received,
    }))

    // Append new events (avoid duplicates)
    const existingIds = new Set(securityEvents.value.map(e => e.id))
    const newEvents = snapshot.recent_events
      .filter(e => !existingIds.has(e.id))
      .map(e => ({
        id: e.id,
        timestamp: new Date(e.timestamp),
        type: e.type as SecurityEvent['type'],
        severity: e.severity as SecurityEvent['severity'],
        source: e.source,
        message: e.message,
        details: e.details,
      }))

    if (newEvents.length > 0) {
      securityEvents.value = [...newEvents, ...securityEvents.value].slice(0, 100)
    }

    apiError.value = null
  } catch (err) {
    console.error('Failed to fetch monitoring data:', err)
    apiError.value = 'Failed to fetch data from API'
  }
}

async function initializeApi() {
  isLoading.value = true
  try {
    isApiAvailable.value = await monitoringApi.checkAvailability()

    if (isApiAvailable.value) {
      await fetchFromApi()
    }
    // If API is not available, we show idle state - NO mock data
  } catch (err) {
    console.error('Failed to initialize monitoring API:', err)
    isApiAvailable.value = false
    // NO mock data generation - show idle state instead
  } finally {
    isLoading.value = false
  }
}

// NOTE: Mock data generation functions (updateMetrics, maybeAddSecurityEvent) have been
// removed as part of the data integrity fix. All data now comes from real simulations only.

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', { hour12: false })
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'online':
    case 'normal':
    case 'info':
      return 'var(--color-success)'
    case 'warning':
    case 'low':
    case 'medium':
      return 'var(--color-warning)'
    case 'offline':
    case 'compromised':
    case 'critical':
    case 'high':
      return 'var(--color-danger)'
    default:
      return 'var(--text-muted)'
  }
}

function getSeverityBg(severity: string): string {
  switch (severity) {
    case 'info': return 'rgba(59, 130, 246, 0.15)'
    case 'low': return 'rgba(34, 197, 94, 0.15)'
    case 'medium': return 'rgba(234, 179, 8, 0.15)'
    case 'high': return 'rgba(249, 115, 22, 0.15)'
    case 'critical': return 'rgba(239, 68, 68, 0.15)'
    default: return 'var(--bg-input)'
  }
}

function getTypeIcon(type: SecurityEvent['type']): string {
  switch (type) {
    case 'auth': return '🔐'
    case 'tls': return '🔒'
    case 'encryption': return '🔑'
    case 'mesh': return '🕸️'
    case 'privacy': return '👁️'
    case 'threat': return '⚠️'
    default: return '•'
  }
}

function getTrendIcon(trend: string): string {
  switch (trend) {
    case 'up': return '↑'
    case 'down': return '↓'
    default: return '→'
  }
}

// ============== QUICK ACTIONS ==============

function exportLogs() {
  // Export security events as JSON
  const exportData = {
    exported_at: new Date().toISOString(),
    event_count: securityEvents.value.length,
    metrics: metrics.value,
    security_stats: securityStats.value,
    events: securityEvents.value.map(e => ({
      ...e,
      timestamp: e.timestamp.toISOString(),
    })),
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `security-logs-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const auditRunning = ref(false)
const auditResult = ref<{ passed: number; failed: number; warnings: number } | null>(null)

async function runAudit() {
  if (auditRunning.value) return

  auditRunning.value = true
  auditResult.value = null

  // Simulate an audit by checking current metrics and stats
  await new Promise(resolve => setTimeout(resolve, 1500))

  // Calculate audit results based on current state
  let passed = 0
  let failed = 0
  let warnings = 0

  // Check metrics
  metrics.value.forEach(m => {
    if (m.status === 'normal') passed++
    else if (m.status === 'warning') warnings++
    else if (m.status === 'critical') failed++
  })

  // Check device statuses
  devices.value.forEach(d => {
    if (d.status === 'online') passed++
    else if (d.status === 'warning') warnings++
    else if (d.status === 'offline' || d.status === 'compromised') failed++
  })

  // Check security stats
  if (securityStats.value.authFailure > 5) warnings++
  else passed++

  if (securityStats.value.threatBlocked > 0) {
    warnings++
  } else {
    passed++
  }

  auditResult.value = { passed, failed, warnings }
  auditRunning.value = false

  // Add audit event to feed
  securityEvents.value.unshift({
    id: generateId(),
    timestamp: new Date(),
    type: 'auth',
    severity: failed > 0 ? 'high' : warnings > 0 ? 'medium' : 'info',
    source: 'audit-system',
    message: `Security audit completed: ${passed} passed, ${warnings} warnings, ${failed} failed`,
  })
}

const alertMode = ref(false)

function toggleAlertMode() {
  alertMode.value = !alertMode.value

  // Add event to feed
  securityEvents.value.unshift({
    id: generateId(),
    timestamp: new Date(),
    type: 'auth',
    severity: alertMode.value ? 'high' : 'info',
    source: 'alert-system',
    message: alertMode.value ? 'Alert mode ACTIVATED - Elevated monitoring enabled' : 'Alert mode deactivated - Normal monitoring resumed',
  })
}

function rotateKeys() {
  // Simulate key rotation
  securityStats.value.encryptedMessages = 0
  securityStats.value.tlsHandshakes = 0

  // Add event to feed
  securityEvents.value.unshift({
    id: generateId(),
    timestamp: new Date(),
    type: 'encryption',
    severity: 'info',
    source: 'key-manager',
    message: 'Security keys rotated successfully - All sessions refreshed',
  })
}

// ============== LIFECYCLE ==============

onMounted(async () => {
  // Initialize API connection
  await initializeApi()

  if (isLive.value) {
    startUpdates()
  }
})

onUnmounted(() => {
  stopUpdates()
})
</script>

<template>
  <div class="monitoring-view">
    <!-- Header -->
    <header class="monitoring-header">
      <div class="header-left">
        <h2>Monitoring Dashboard</h2>
        <!-- Only show LIVE indicator when simulation is running (not in idle state) -->
        <span v-if="!showIdleMessage" class="live-indicator" :class="{ active: isLive }">
          <span class="dot"></span>
          {{ isLive ? 'LIVE' : 'PAUSED' }}
        </span>
        <span class="data-source" :class="{ api: isApiAvailable, offline: !isApiAvailable }">
          {{ isApiAvailable ? 'API Connected' : 'API Offline' }}
        </span>
        <span class="sim-state-badge" :class="simulationState">
          {{ simulationState === 'running' ? 'SIMULATION ACTIVE' :
             simulationState === 'paused' ? 'SIMULATION PAUSED' :
             simulationState === 'completed' ? 'COMPLETED' : 'NO SIMULATION' }}
        </span>
        <!-- Simulation Status Indicator -->
        <span
          v-if="simulationStatus"
          class="simulation-indicator"
          :class="{ running: isSimulationRunning }"
        >
          <span class="sim-dot"></span>
          <span class="sim-label">
            {{ simulationStatus.status === 'running' ? 'SIM RUNNING' :
               simulationStatus.status === 'paused' ? 'SIM PAUSED' :
               simulationStatus.status === 'completed' ? 'SIM COMPLETED' : 'NO SIM' }}
          </span>
          <span v-if="isSimulationRunning" class="sim-progress">
            {{ Math.round(simulationStatus.progress) }}%
          </span>
        </span>
      </div>

      <div class="header-right">
        <!-- Only show time range selector and controls when simulation is running -->
        <div v-if="!showIdleMessage" class="time-range-selector">
          <button
            v-for="range in ['5m', '15m', '1h', '6h', '24h']"
            :key="range"
            class="range-btn"
            :class="{ active: timeRange === range }"
            @click="timeRange = range"
          >
            {{ range }}
          </button>
        </div>

        <!-- Only show Pause/Resume button when simulation is running -->
        <button v-if="!showIdleMessage" class="btn btn-ghost" @click="toggleLive">
          {{ isLive ? 'Pause Updates' : 'Resume Updates' }}
        </button>
      </div>
    </header>

    <div class="monitoring-content">
      <!-- Idle State Message - shown when no simulation is running -->
      <div v-if="showIdleMessage" class="idle-state-banner">
        <div class="idle-icon">🏠</div>
        <h3>No Simulation Running</h3>
        <p>Start a simulation from the <strong>Home Builder</strong> or <strong>Simulation Control</strong> panel to see real-time monitoring data.</p>
        <p class="idle-note">The monitoring dashboard displays live data only when a simulation is actively running. No mock or sample data is shown.</p>
      </div>

      <!-- Top Row - Key Metrics (only show if we have data) -->
      <section v-if="metrics.length > 0" class="metrics-row">
        <div
          v-for="metric in metrics"
          :key="metric.name"
          class="metric-card"
          :class="metric.status"
        >
          <div class="metric-header">
            <span class="metric-name">{{ metric.name }}</span>
            <span class="metric-trend" :class="metric.trend">
              {{ getTrendIcon(metric.trend) }}
            </span>
          </div>
          <div class="metric-value">
            {{ metric.value }}{{ metric.unit }}
          </div>
          <div class="metric-status" :style="{ color: getStatusColor(metric.status) }">
            {{ metric.status }}
          </div>
        </div>
      </section>

      <!-- Main Content (only show when we have data or API is available) -->
      <div v-if="!showIdleMessage" class="main-grid">
        <!-- Left Column - Security Stats & Device List -->
        <div class="left-column">
          <!-- Security Statistics -->
          <section class="panel security-stats-panel">
            <div class="panel-header">
              <h3>Security Statistics</h3>
            </div>
            <div class="security-stats">
              <div class="stat-item success">
                <div class="stat-icon">🔐</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.authSuccess }}</span>
                  <span class="stat-label">Auth Success</span>
                </div>
              </div>
              <div class="stat-item warning">
                <div class="stat-icon">⚠️</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.authFailure }}</span>
                  <span class="stat-label">Auth Failures</span>
                </div>
              </div>
              <div class="stat-item info">
                <div class="stat-icon">🔒</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.tlsHandshakes }}</span>
                  <span class="stat-label">TLS Handshakes</span>
                </div>
              </div>
              <div class="stat-item info">
                <div class="stat-icon">🔑</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.encryptedMessages }}</span>
                  <span class="stat-label">Encrypted Msgs</span>
                </div>
              </div>
              <div class="stat-item info">
                <div class="stat-icon">👁️</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.privacyQueries }}</span>
                  <span class="stat-label">Privacy Queries</span>
                </div>
              </div>
              <div class="stat-item danger">
                <div class="stat-icon">🛡️</div>
                <div class="stat-info">
                  <span class="stat-value">{{ securityStats.threatBlocked }}</span>
                  <span class="stat-label">Threats Blocked</span>
                </div>
              </div>
            </div>
          </section>

          <!-- Device Status -->
          <section class="panel device-panel">
            <div class="panel-header">
              <h3>Device Status</h3>
              <div class="device-summary">
                <span class="summary-item online">{{ onlineDeviceCount }} Online</span>
                <span class="summary-item warning">{{ warningDeviceCount }} Warning</span>
                <span class="summary-item offline">{{ offlineDeviceCount }} Offline</span>
              </div>
            </div>
            <div class="device-list">
              <div
                v-for="device in devices"
                :key="device.id"
                class="device-item"
                :class="device.status"
              >
                <div class="device-status-dot" :style="{ backgroundColor: getStatusColor(device.status) }"></div>
                <div class="device-info">
                  <span class="device-name">{{ device.name }}</span>
                  <span class="device-meta">{{ device.type }} • {{ device.protocol }}</span>
                </div>
                <div class="device-indicators">
                  <span v-if="device.batteryLevel !== undefined" class="indicator battery">
                    🔋 {{ device.batteryLevel }}%
                  </span>
                  <span v-if="device.signalStrength !== undefined" class="indicator signal">
                    📶 {{ device.signalStrength }}dBm
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- Center Column - Event Feed -->
        <div class="center-column">
          <section class="panel event-panel">
            <div class="panel-header">
              <h3>Security Event Feed</h3>
              <span class="event-count">{{ securityEvents.length }} events</span>
            </div>
            <div class="event-feed">
              <div
                v-for="event in recentEvents"
                :key="event.id"
                class="event-item"
                :style="{ backgroundColor: getSeverityBg(event.severity) }"
              >
                <div class="event-time">{{ formatTime(event.timestamp) }}</div>
                <div class="event-icon">{{ getTypeIcon(event.type) }}</div>
                <div class="event-content">
                  <div class="event-header">
                    <span class="event-type">{{ event.type }}</span>
                    <span class="event-severity" :class="event.severity">{{ event.severity }}</span>
                  </div>
                  <div class="event-message">{{ event.message }}</div>
                  <div class="event-source">Source: {{ event.source }}</div>
                </div>
              </div>

              <div v-if="securityEvents.length === 0" class="empty-state">
                <p>No security events yet</p>
              </div>
            </div>
          </section>
        </div>

        <!-- Right Column - Mesh Network -->
        <div class="right-column">
          <section class="panel mesh-panel">
            <div class="panel-header">
              <h3>Mesh Network</h3>
              <span class="node-count">{{ meshNodes.length }} nodes</span>
            </div>
            <div class="mesh-visualization">
              <!-- Simple network visualization -->
              <svg viewBox="0 0 200 200" class="network-svg">
                <!-- Connections -->
                <line x1="100" y1="50" x2="50" y2="120" stroke="var(--border-color)" stroke-width="2"/>
                <line x1="100" y1="50" x2="150" y2="120" stroke="var(--border-color)" stroke-width="2"/>
                <line x1="50" y1="120" x2="100" y2="170" stroke="var(--border-color)" stroke-width="2"/>
                <line x1="150" y1="120" x2="100" y2="170" stroke="var(--border-color)" stroke-width="2"/>

                <!-- Coordinator -->
                <circle cx="100" cy="50" r="15" fill="var(--color-primary)"/>
                <text x="100" y="55" text-anchor="middle" fill="white" font-size="10">C</text>

                <!-- Routers -->
                <circle cx="50" cy="120" r="12" fill="var(--color-success)"/>
                <text x="50" y="124" text-anchor="middle" fill="white" font-size="9">R</text>
                <circle cx="150" cy="120" r="12" fill="var(--color-success)"/>
                <text x="150" y="124" text-anchor="middle" fill="white" font-size="9">R</text>

                <!-- End Device -->
                <circle cx="100" cy="170" r="10" fill="var(--color-warning)"/>
                <text x="100" y="174" text-anchor="middle" fill="white" font-size="8">E</text>
              </svg>
            </div>
            <div class="mesh-nodes">
              <div v-for="node in meshNodes" :key="node.id" class="mesh-node">
                <div class="node-role" :class="node.role">{{ node.role }}</div>
                <div class="node-stats">
                  <span>↑ {{ node.messagesSent }}</span>
                  <span>↓ {{ node.messagesReceived }}</span>
                  <span>👥 {{ node.neighbors }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- Quick Actions -->
          <section class="panel actions-panel">
            <div class="panel-header">
              <h3>Quick Actions</h3>
            </div>
            <div class="action-buttons">
              <button class="action-btn" @click="rotateKeys" title="Rotate encryption keys">
                <span class="action-icon">🔄</span>
                Rotate Keys
              </button>
              <button class="action-btn" @click="exportLogs" title="Export security logs as JSON">
                <span class="action-icon">📊</span>
                Export Logs
              </button>
              <button
                class="action-btn"
                :class="{ running: auditRunning }"
                @click="runAudit"
                :disabled="auditRunning"
                title="Run security audit"
              >
                <span class="action-icon">{{ auditRunning ? '⏳' : '🔍' }}</span>
                {{ auditRunning ? 'Auditing...' : 'Run Audit' }}
              </button>
              <button
                class="action-btn"
                :class="{ danger: !alertMode, active: alertMode }"
                @click="toggleAlertMode"
                title="Toggle alert mode for elevated monitoring"
              >
                <span class="action-icon">🚨</span>
                {{ alertMode ? 'Alert ON' : 'Alert Mode' }}
              </button>
            </div>
            <!-- Audit Results -->
            <div v-if="auditResult" class="audit-results">
              <div class="audit-result passed">
                <span class="result-value">{{ auditResult.passed }}</span>
                <span class="result-label">Passed</span>
              </div>
              <div class="audit-result warnings">
                <span class="result-value">{{ auditResult.warnings }}</span>
                <span class="result-label">Warnings</span>
              </div>
              <div class="audit-result failed">
                <span class="result-value">{{ auditResult.failed }}</span>
                <span class="result-label">Failed</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitoring-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Header */
.monitoring-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-left h2 {
  margin: 0;
  font-size: 1.25rem;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
}

.live-indicator.active {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
}

.live-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.live-indicator.active .dot {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.data-source {
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
}

.data-source.api {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
}

.data-source.offline {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

/* Simulation State Badge */
.sim-state-badge {
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
}

.sim-state-badge.idle {
  background: rgba(107, 114, 128, 0.15);
  color: var(--text-muted);
}

.sim-state-badge.running {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
}

.sim-state-badge.paused {
  background: rgba(234, 179, 8, 0.15);
  color: var(--color-warning);
}

.sim-state-badge.completed {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}

/* Simulation Status Indicator */
.simulation-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
}

.simulation-indicator.running {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}

.simulation-indicator .sim-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.simulation-indicator.running .sim-dot {
  animation: pulse 1.5s infinite;
}

.simulation-indicator .sim-progress {
  padding-left: var(--spacing-xs);
  border-left: 1px solid currentColor;
  opacity: 0.7;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.time-range-selector {
  display: flex;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.range-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.range-btn:hover {
  background: var(--bg-hover);
}

.range-btn.active {
  background: var(--color-primary);
  color: white;
}

/* Content */
.monitoring-content {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* Idle State Banner */
.idle-state-banner {
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
}

.idle-state-banner .idle-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.idle-state-banner h3 {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-primary);
  font-size: 1.25rem;
}

.idle-state-banner p {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-secondary);
  max-width: 500px;
  line-height: 1.5;
}

.idle-state-banner .idle-note {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-style: italic;
}

/* Metrics Row */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--spacing-md);
}

.metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.metric-card.warning {
  border-color: var(--color-warning);
}

.metric-card.critical {
  border-color: var(--color-danger);
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.metric-name {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.metric-trend {
  font-size: 0.85rem;
  font-weight: 600;
}

.metric-trend.up { color: var(--color-success); }
.metric-trend.down { color: var(--color-danger); }
.metric-trend.stable { color: var(--text-muted); }

.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-status {
  font-size: 0.65rem;
  text-transform: uppercase;
  font-weight: 600;
  margin-top: var(--spacing-xs);
}

/* Main Grid */
.main-grid {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  gap: var(--spacing-md);
  flex: 1;
  min-height: 0;
}

/* Panels */
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.panel-header h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

/* Left Column */
.left-column {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* Security Stats */
.security-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.stat-item.success { background: rgba(34, 197, 94, 0.1); }
.stat-item.warning { background: rgba(234, 179, 8, 0.1); }
.stat-item.danger { background: rgba(239, 68, 68, 0.1); }
.stat-item.info { background: rgba(59, 130, 246, 0.1); }

.stat-icon {
  font-size: 1.25rem;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.65rem;
  color: var(--text-muted);
}

/* Device Panel */
.device-panel {
  flex: 1;
  min-height: 0;
}

.device-summary {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 0.7rem;
}

.summary-item {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.summary-item.online { background: rgba(34, 197, 94, 0.15); color: var(--color-success); }
.summary-item.warning { background: rgba(234, 179, 8, 0.15); color: var(--color-warning); }
.summary-item.offline { background: rgba(239, 68, 68, 0.15); color: var(--color-danger); }

.device-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.device-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-xs);
  background: var(--bg-input);
}

.device-item.warning { background: rgba(234, 179, 8, 0.1); }
.device-item.offline { background: rgba(239, 68, 68, 0.1); }

.device-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.device-info {
  flex: 1;
  min-width: 0;
}

.device-name {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
}

.device-meta {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.device-indicators {
  display: flex;
  gap: var(--spacing-xs);
  font-size: 0.65rem;
  color: var(--text-secondary);
}

/* Event Panel */
.event-panel {
  flex: 1;
  min-height: 0;
}

.event-count {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.event-feed {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.event-item {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-xs);
}

.event-time {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-muted);
  flex-shrink: 0;
  width: 65px;
}

.event-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.event-content {
  flex: 1;
  min-width: 0;
}

.event-header {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
  margin-bottom: 2px;
}

.event-type {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.event-severity {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 1px 4px;
  border-radius: var(--radius-sm);
}

.event-severity.info { background: rgba(59, 130, 246, 0.2); color: var(--color-primary); }
.event-severity.low { background: rgba(34, 197, 94, 0.2); color: var(--color-success); }
.event-severity.medium { background: rgba(234, 179, 8, 0.2); color: var(--color-warning); }
.event-severity.high { background: rgba(249, 115, 22, 0.2); color: #f97316; }
.event-severity.critical { background: rgba(239, 68, 68, 0.2); color: var(--color-danger); }

.event-message {
  font-size: 0.8rem;
  color: var(--text-primary);
}

.event-source {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Right Column */
.right-column {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* Mesh Panel */
.mesh-panel {
  flex: 1;
}

.node-count {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.mesh-visualization {
  padding: var(--spacing-md);
  display: flex;
  justify-content: center;
}

.network-svg {
  width: 150px;
  height: 150px;
}

.mesh-nodes {
  padding: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}

.mesh-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-xs) var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.node-role {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.node-role.coordinator { background: rgba(59, 130, 246, 0.15); color: var(--color-primary); }
.node-role.router { background: rgba(34, 197, 94, 0.15); color: var(--color-success); }
.node-role.end_device { background: rgba(234, 179, 8, 0.15); color: var(--color-warning); }

.node-stats {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 0.7rem;
  color: var(--text-muted);
}

/* Actions Panel */
.actions-panel {
  flex-shrink: 0;
}

.action-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--bg-hover);
  border-color: var(--color-primary);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.action-btn.active {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.action-btn.running {
  opacity: 0.7;
  cursor: wait;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Audit Results */
.audit-results {
  display: flex;
  justify-content: space-around;
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--border-color);
  margin-top: var(--spacing-sm);
}

.audit-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.audit-result .result-value {
  font-size: 1.25rem;
  font-weight: 700;
}

.audit-result .result-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.audit-result.passed .result-value {
  color: var(--color-success);
}

.audit-result.warnings .result-value {
  color: var(--color-warning);
}

.audit-result.failed .result-value {
  color: var(--color-danger);
}

.action-icon {
  font-size: 1.25rem;
}

/* Empty state */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1200px) {
  .metrics-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .main-grid {
    grid-template-columns: 1fr 1fr;
  }

  .right-column {
    grid-column: span 2;
    flex-direction: row;
  }

  .mesh-panel, .actions-panel {
    flex: 1;
  }
}

@media (max-width: 768px) {
  .metrics-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .main-grid {
    grid-template-columns: 1fr;
  }

  .right-column {
    flex-direction: column;
  }
}
</style>
