<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  historyApi,
  type HistoricalEvent as BackendEvent,
  type SimulationRun as BackendSimulation,
  type TimelinePoint,
} from '@/services/historyApi'

// ============== TYPES ==============

interface HistoricalEvent {
  id: string
  timestamp: Date
  category: 'simulation' | 'security' | 'device' | 'network' | 'user'
  type: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  source: string
  message: string
  details: Record<string, unknown>
  tags: string[]
}

interface SimulationRun {
  id: string
  name: string
  startTime: Date
  endTime: Date
  duration: number
  status: 'completed' | 'failed' | 'aborted'
  totalEvents: number
  threatsDetected: number
  threatsBlocked: number
  compromisedDevices: number
  homeConfig: string
  threatScenario: string
}

interface TimelineDataPoint {
  timestamp: Date
  value: number
  category: string
}

// ============== STATE ==============

const searchQuery = ref('')
const selectedCategory = ref<string | null>(null)
const selectedSeverity = ref<string | null>(null)
const dateRange = ref({ start: null as Date | null, end: null as Date | null })
const activeTab = ref<'events' | 'simulations' | 'analytics'>('events')

// Historical data
const events = ref<HistoricalEvent[]>([])
const simulations = ref<SimulationRun[]>([])
const timelineData = ref<TimelineDataPoint[]>([])

// Loading states
const isLoading = ref(false)
const isBackendAvailable = ref(false)
const loadError = ref<string | null>(null)

// Pagination
const currentPage = ref(1)
const itemsPerPage = 50
const totalEvents = ref(0)
const totalPages = ref(1)

// Selected event for details
const selectedEvent = ref<HistoricalEvent | null>(null)

// ============== COMPUTED ==============

const filteredEvents = computed(() => {
  let result = events.value

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(e =>
      e.message.toLowerCase().includes(query) ||
      e.source.toLowerCase().includes(query) ||
      e.type.toLowerCase().includes(query) ||
      e.tags.some(t => t.toLowerCase().includes(query))
    )
  }

  if (selectedCategory.value) {
    result = result.filter(e => e.category === selectedCategory.value)
  }

  if (selectedSeverity.value) {
    result = result.filter(e => e.severity === selectedSeverity.value)
  }

  // Apply date range filter for client-side filtering
  if (dateRange.value.start) {
    const startDate = new Date(dateRange.value.start)
    startDate.setHours(0, 0, 0, 0)
    result = result.filter(e => e.timestamp >= startDate)
  }

  if (dateRange.value.end) {
    const endDate = new Date(dateRange.value.end)
    endDate.setHours(23, 59, 59, 999)
    result = result.filter(e => e.timestamp <= endDate)
  }

  return result
})

const paginatedEvents = computed(() => {
  // When using backend, pagination is handled server-side
  if (isBackendAvailable.value) {
    return events.value
  }
  // Fallback to client-side pagination
  const start = (currentPage.value - 1) * itemsPerPage
  const end = start + itemsPerPage
  return filteredEvents.value.slice(start, end)
})

const categoryStats = computed(() => {
  const stats: Record<string, number> = {}
  events.value.forEach(e => {
    stats[e.category] = (stats[e.category] || 0) + 1
  })
  return stats
})

const severityStats = computed(() => {
  const stats: Record<string, number> = {}
  events.value.forEach(e => {
    stats[e.severity] = (stats[e.severity] || 0) + 1
  })
  return stats
})

// ============== METHODS ==============

function convertBackendEvent(backendEvent: BackendEvent): HistoricalEvent {
  return {
    id: backendEvent.id,
    timestamp: new Date(backendEvent.timestamp),
    category: backendEvent.category as HistoricalEvent['category'],
    type: backendEvent.type,
    severity: backendEvent.severity as HistoricalEvent['severity'],
    source: backendEvent.source,
    message: backendEvent.message,
    details: backendEvent.details,
    tags: backendEvent.tags,
  }
}

function convertBackendSimulation(backendSim: BackendSimulation): SimulationRun {
  return {
    id: backendSim.id,
    name: backendSim.name,
    startTime: new Date(backendSim.start_time),
    endTime: backendSim.end_time ? new Date(backendSim.end_time) : new Date(),
    duration: backendSim.duration_minutes,
    status: backendSim.status,
    totalEvents: backendSim.total_events,
    threatsDetected: backendSim.threats_detected,
    threatsBlocked: backendSim.threats_blocked,
    compromisedDevices: backendSim.compromised_devices,
    homeConfig: backendSim.home_config,
    threatScenario: backendSim.threat_scenario || 'None',
  }
}

async function loadFromBackend() {
  isLoading.value = true
  loadError.value = null

  try {
    // Check availability
    isBackendAvailable.value = await historyApi.checkAvailability()

    if (!isBackendAvailable.value) {
      loadError.value = 'Backend not available. Please ensure the backend server is running to view history data.'
      // No sample data - show empty state
      events.value = []
      simulations.value = []
      timelineData.value = []
      totalEvents.value = 0
      totalPages.value = 0
      return
    }

    // Load events
    const eventsResponse = await historyApi.getEvents({
      page: currentPage.value,
      page_size: itemsPerPage,
      category: selectedCategory.value || undefined,
      severity: selectedSeverity.value || undefined,
      search: searchQuery.value || undefined,
      start_date: dateRange.value.start ? dateRange.value.start.toISOString() : undefined,
      end_date: dateRange.value.end ? dateRange.value.end.toISOString() : undefined,
    })

    events.value = eventsResponse.events.map(convertBackendEvent)
    totalEvents.value = eventsResponse.total
    totalPages.value = eventsResponse.total_pages

    // Load simulations
    const simsResponse = await historyApi.getSimulations()
    simulations.value = simsResponse.simulations.map(convertBackendSimulation)

    // Load analytics
    const analyticsResponse = await historyApi.getAnalytics(7)
    timelineData.value = analyticsResponse.timeline_data.map((p: TimelinePoint) => ({
      timestamp: new Date(p.timestamp),
      value: p.value,
      category: p.category,
    }))

    // If no data, show message but don't generate sample
    if (events.value.length === 0 && simulations.value.length === 0) {
      loadError.value = 'No history data yet. Run a simulation and save it as an experiment to see history data.'
    }

  } catch (error) {
    console.error('Failed to load history data:', error)
    loadError.value = 'Failed to load history data. Please check the backend connection and try again.'
    // No sample data - show empty state
    events.value = []
    simulations.value = []
    timelineData.value = []
    totalEvents.value = 0
    totalPages.value = 0
  } finally {
    isLoading.value = false
  }
}

async function refreshEvents() {
  if (!isBackendAvailable.value) return

  isLoading.value = true
  try {
    const eventsResponse = await historyApi.getEvents({
      page: currentPage.value,
      page_size: itemsPerPage,
      category: selectedCategory.value || undefined,
      severity: selectedSeverity.value || undefined,
      search: searchQuery.value || undefined,
      start_date: dateRange.value.start ? dateRange.value.start.toISOString() : undefined,
      end_date: dateRange.value.end ? dateRange.value.end.toISOString() : undefined,
    })

    events.value = eventsResponse.events.map(convertBackendEvent)
    totalEvents.value = eventsResponse.total
    totalPages.value = eventsResponse.total_pages
  } catch (error) {
    console.error('Failed to refresh events:', error)
  } finally {
    isLoading.value = false
  }
}

// Watch for filter changes
watch([selectedCategory, selectedSeverity], () => {
  currentPage.value = 1
  if (isBackendAvailable.value) {
    refreshEvents()
  }
})

// Watch for date range changes
watch(dateRange, () => {
  currentPage.value = 1
  if (isBackendAvailable.value) {
    refreshEvents()
  }
}, { deep: true })

watch(currentPage, () => {
  if (isBackendAvailable.value) {
    refreshEvents()
  }
})

// RESEARCH INTEGRITY: No sample data generation functions.
// All data must come from actual backend operations.

function formatDateTime(date: Date): string {
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours > 0) {
    return `${hours}h ${mins}m`
  }
  return `${mins}m`
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'info': return 'var(--color-primary)'
    case 'low': return 'var(--color-success)'
    case 'medium': return 'var(--color-warning)'
    case 'high': return '#f97316'
    case 'critical': return 'var(--color-danger)'
    default: return 'var(--text-muted)'
  }
}

function getCategoryIcon(category: string): string {
  switch (category) {
    case 'simulation': return '🎮'
    case 'security': return '🔐'
    case 'device': return '📱'
    case 'network': return '🕸️'
    case 'user': return '👤'
    default: return '•'
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'var(--color-success)'
    case 'failed': return 'var(--color-danger)'
    case 'aborted': return 'var(--color-warning)'
    default: return 'var(--text-muted)'
  }
}

function clearFilters() {
  searchQuery.value = ''
  selectedCategory.value = null
  selectedSeverity.value = null
  dateRange.value = { start: null, end: null }
  currentPage.value = 1
  if (isBackendAvailable.value) {
    refreshEvents()
  }
}

function exportData() {
  const data = {
    events: filteredEvents.value,
    simulations: simulations.value,
    exportedAt: new Date().toISOString(),
    filters: {
      searchQuery: searchQuery.value,
      category: selectedCategory.value,
      severity: selectedSeverity.value,
    },
    source: isBackendAvailable.value ? 'backend' : 'sample',
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `history-export-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function showEventDetails(event: HistoricalEvent) {
  selectedEvent.value = event
}

// Date range helpers
function formatDateForInput(date: Date): string {
  return date.toISOString().split('T')[0]
}

function setStartDate(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.value) {
    dateRange.value.start = new Date(input.value)
  } else {
    dateRange.value.start = null
  }
}

function setEndDate(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.value) {
    dateRange.value.end = new Date(input.value)
  } else {
    dateRange.value.end = null
  }
}

function closeEventDetails() {
  selectedEvent.value = null
}

// ============== LIFECYCLE ==============

onMounted(() => {
  loadFromBackend()
})
</script>

<template>
  <div class="history-view">
    <!-- Header -->
    <header class="history-header">
      <div class="header-left">
        <h2>Historical Data Explorer</h2>
        <span v-if="!isBackendAvailable && !isLoading" class="data-source-badge sample">
          Sample Data
        </span>
        <span v-else-if="isBackendAvailable" class="data-source-badge live">
          Live Data
        </span>
      </div>

      <div class="header-right">
        <button class="btn btn-ghost" @click="loadFromBackend" :disabled="isLoading">
          <span>🔄</span> {{ isLoading ? 'Loading...' : 'Refresh' }}
        </button>
        <button class="btn btn-ghost" @click="exportData">
          <span>📥</span> Export
        </button>
      </div>
    </header>

    <!-- Info Banner -->
    <div v-if="loadError" class="info-banner">
      <span>ℹ️</span> {{ loadError }}
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'events' }"
        @click="activeTab = 'events'"
      >
        Events
        <span class="tab-count">{{ totalEvents }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'simulations' }"
        @click="activeTab = 'simulations'"
      >
        Simulations
        <span class="tab-count">{{ simulations.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'analytics' }"
        @click="activeTab = 'analytics'"
      >
        Analytics
      </button>
    </div>

    <div class="history-content">
      <!-- Loading Spinner -->
      <div v-if="isLoading" class="loading-spinner">
        <div class="spinner"></div>
        <span>Loading history data...</span>
      </div>

      <!-- Events Tab -->
      <div v-else-if="activeTab === 'events'" class="events-tab">
        <!-- Filters -->
        <div class="filters-panel">
          <div class="search-box">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search events..."
              class="search-input"
              @keyup.enter="refreshEvents"
            />
          </div>

          <div class="filter-group">
            <label>Category:</label>
            <select v-model="selectedCategory" class="filter-select">
              <option :value="null">All</option>
              <option value="simulation">Simulation</option>
              <option value="security">Security</option>
              <option value="device">Device</option>
              <option value="network">Network</option>
              <option value="user">User</option>
            </select>
          </div>

          <div class="filter-group">
            <label>Severity:</label>
            <select v-model="selectedSeverity" class="filter-select">
              <option :value="null">All</option>
              <option value="info">Info</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div class="filter-group date-range-group">
            <label>Date Range:</label>
            <div class="date-range-inputs">
              <input
                type="date"
                :value="dateRange.start ? formatDateForInput(dateRange.start) : ''"
                @input="setStartDate($event)"
                class="date-input"
                placeholder="Start date"
              />
              <span class="date-separator">to</span>
              <input
                type="date"
                :value="dateRange.end ? formatDateForInput(dateRange.end) : ''"
                @input="setEndDate($event)"
                class="date-input"
                placeholder="End date"
              />
            </div>
          </div>

          <button class="btn btn-ghost btn-sm" @click="clearFilters">Clear Filters</button>
        </div>

        <!-- Stats Cards -->
        <div class="stats-cards">
          <div class="stat-card">
            <div class="stat-label">Total Events</div>
            <div class="stat-value">{{ totalEvents }}</div>
          </div>
          <div v-for="(count, category) in categoryStats" :key="category" class="stat-card">
            <div class="stat-label">
              <span>{{ getCategoryIcon(category as string) }}</span>
              {{ category }}
            </div>
            <div class="stat-value">{{ count }}</div>
          </div>
        </div>

        <!-- Events Table -->
        <div class="events-table-container">
          <table class="events-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Source</th>
                <th>Message</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="event in paginatedEvents"
                :key="event.id"
                @click="showEventDetails(event)"
              >
                <td class="timestamp">{{ formatDateTime(event.timestamp) }}</td>
                <td>
                  <span class="category-badge">
                    {{ getCategoryIcon(event.category) }} {{ event.category }}
                  </span>
                </td>
                <td>
                  <span
                    class="severity-badge"
                    :style="{ backgroundColor: getSeverityColor(event.severity) + '20', color: getSeverityColor(event.severity) }"
                  >
                    {{ event.severity }}
                  </span>
                </td>
                <td class="source">{{ event.source }}</td>
                <td class="message">{{ event.message }}</td>
                <td class="tags">
                  <span v-for="tag in event.tags" :key="tag" class="tag">{{ tag }}</span>
                </td>
              </tr>
              <tr v-if="paginatedEvents.length === 0">
                <td colspan="6" class="no-data">No events found</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div class="pagination">
          <button
            class="btn btn-ghost btn-sm"
            :disabled="currentPage === 1"
            @click="currentPage--"
          >
            Previous
          </button>
          <span class="page-info">Page {{ currentPage }} of {{ totalPages }}</span>
          <button
            class="btn btn-ghost btn-sm"
            :disabled="currentPage === totalPages"
            @click="currentPage++"
          >
            Next
          </button>
        </div>
      </div>

      <!-- Simulations Tab -->
      <div v-else-if="activeTab === 'simulations'" class="simulations-tab">
        <div v-if="simulations.length === 0" class="no-data-message">
          <p>No simulation runs found.</p>
          <p>Run a simulation and save it as an experiment to see it here.</p>
        </div>
        <div v-else class="simulations-grid">
          <div
            v-for="sim in simulations"
            :key="sim.id"
            class="simulation-card"
            :class="sim.status"
          >
            <div class="sim-header">
              <h4>{{ sim.name }}</h4>
              <span class="sim-status" :style="{ color: getStatusColor(sim.status) }">
                {{ sim.status }}
              </span>
            </div>

            <div class="sim-time">
              <div class="time-item">
                <span class="label">Started:</span>
                <span class="value">{{ formatDateTime(sim.startTime) }}</span>
              </div>
              <div class="time-item">
                <span class="label">Duration:</span>
                <span class="value">{{ formatDuration(sim.duration) }}</span>
              </div>
            </div>

            <div class="sim-stats">
              <div class="sim-stat">
                <span class="stat-num">{{ sim.totalEvents }}</span>
                <span class="stat-label">Events</span>
              </div>
              <div class="sim-stat detected">
                <span class="stat-num">{{ sim.threatsDetected }}</span>
                <span class="stat-label">Detected</span>
              </div>
              <div class="sim-stat blocked">
                <span class="stat-num">{{ sim.threatsBlocked }}</span>
                <span class="stat-label">Blocked</span>
              </div>
              <div class="sim-stat compromised">
                <span class="stat-num">{{ sim.compromisedDevices }}</span>
                <span class="stat-label">Compromised</span>
              </div>
            </div>

            <div class="sim-configs">
              <span class="config-item">🏠 {{ sim.homeConfig }}</span>
              <span class="config-item">⚔️ {{ sim.threatScenario }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Analytics Tab -->
      <div v-else-if="activeTab === 'analytics'" class="analytics-tab">
        <div class="analytics-grid">
          <!-- Severity Distribution -->
          <div class="analytics-card">
            <h4>Severity Distribution</h4>
            <div class="severity-bars">
              <div v-for="(count, severity) in severityStats" :key="severity" class="severity-bar">
                <span class="bar-label">{{ severity }}</span>
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{
                      width: `${totalEvents > 0 ? (count as number / totalEvents) * 100 : 0}%`,
                      backgroundColor: getSeverityColor(severity as string)
                    }"
                  ></div>
                </div>
                <span class="bar-value">{{ count }}</span>
              </div>
              <div v-if="Object.keys(severityStats).length === 0" class="no-data">
                No severity data available
              </div>
            </div>
          </div>

          <!-- Category Distribution -->
          <div class="analytics-card">
            <h4>Category Distribution</h4>
            <div class="category-chart">
              <div v-for="(count, category) in categoryStats" :key="category" class="category-item">
                <span class="cat-icon">{{ getCategoryIcon(category as string) }}</span>
                <span class="cat-name">{{ category }}</span>
                <span class="cat-count">{{ count }}</span>
                <div class="cat-bar">
                  <div
                    class="cat-fill"
                    :style="{ width: `${totalEvents > 0 ? (count as number / totalEvents) * 100 : 0}%` }"
                  ></div>
                </div>
              </div>
              <div v-if="Object.keys(categoryStats).length === 0" class="no-data">
                No category data available
              </div>
            </div>
          </div>

          <!-- Timeline -->
          <div class="analytics-card timeline-card">
            <h4>Events Over Time (Last 7 Days)</h4>
            <div class="timeline-chart">
              <svg v-if="timelineData.length > 0" viewBox="0 0 700 150" class="timeline-svg">
                <!-- Grid lines -->
                <line v-for="i in 5" :key="i" :y1="i * 30" :y2="i * 30" x1="0" x2="700" stroke="var(--border-color)" stroke-dasharray="4"/>

                <!-- Data points and line -->
                <polyline
                  :points="timelineData.map((p, i) => `${i * (700 / Math.max(1, timelineData.length - 1))},${150 - Math.min(p.value * 2, 140)}`).join(' ')"
                  fill="none"
                  stroke="var(--color-primary)"
                  stroke-width="2"
                />

                <!-- Area fill -->
                <polygon
                  :points="`0,150 ${timelineData.map((p, i) => `${i * (700 / Math.max(1, timelineData.length - 1))},${150 - Math.min(p.value * 2, 140)}`).join(' ')} 700,150`"
                  fill="url(#gradient)"
                  opacity="0.3"
                />

                <defs>
                  <linearGradient id="gradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="var(--color-primary)"/>
                    <stop offset="100%" stop-color="transparent"/>
                  </linearGradient>
                </defs>
              </svg>
              <div v-else class="no-data">No timeline data available</div>
            </div>
          </div>

          <!-- Summary Stats -->
          <div class="analytics-card summary-card">
            <h4>Summary Statistics</h4>
            <div class="summary-stats">
              <div class="summary-item">
                <span class="sum-label">Total Events</span>
                <span class="sum-value">{{ totalEvents }}</span>
              </div>
              <div class="summary-item">
                <span class="sum-label">Total Simulations</span>
                <span class="sum-value">{{ simulations.length }}</span>
              </div>
              <div class="summary-item">
                <span class="sum-label">Avg Events/Simulation</span>
                <span class="sum-value">
                  {{ simulations.length > 0 ? Math.round(simulations.reduce((a, s) => a + s.totalEvents, 0) / simulations.length) : 0 }}
                </span>
              </div>
              <div class="summary-item">
                <span class="sum-label">Total Threats Blocked</span>
                <span class="sum-value">
                  {{ simulations.reduce((a, s) => a + s.threatsBlocked, 0) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Event Details Modal -->
    <div v-if="selectedEvent" class="modal-overlay" @click="closeEventDetails">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Event Details</h3>
          <button class="close-btn" @click="closeEventDetails">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-row">
            <span class="detail-label">ID:</span>
            <span class="detail-value mono">{{ selectedEvent.id }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Timestamp:</span>
            <span class="detail-value">{{ formatDateTime(selectedEvent.timestamp) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Category:</span>
            <span class="detail-value">{{ getCategoryIcon(selectedEvent.category) }} {{ selectedEvent.category }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Type:</span>
            <span class="detail-value">{{ selectedEvent.type }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Severity:</span>
            <span class="detail-value">
              <span
                class="severity-badge"
                :style="{ backgroundColor: getSeverityColor(selectedEvent.severity) + '20', color: getSeverityColor(selectedEvent.severity) }"
              >
                {{ selectedEvent.severity }}
              </span>
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Source:</span>
            <span class="detail-value">{{ selectedEvent.source }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Message:</span>
            <span class="detail-value">{{ selectedEvent.message }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Tags:</span>
            <span class="detail-value">
              <span v-for="tag in selectedEvent.tags" :key="tag" class="tag">{{ tag }}</span>
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Details:</span>
            <pre class="detail-json">{{ JSON.stringify(selectedEvent.details, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Header */
.history-header {
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

.header-right {
  display: flex;
  gap: var(--spacing-sm);
}

.data-source-badge {
  padding: 4px 8px;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.data-source-badge.sample {
  background: var(--color-warning);
  color: #000;
}

.data-source-badge.live {
  background: var(--color-success);
  color: #fff;
}

/* Info Banner */
.info-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-lg);
  background: rgba(59, 130, 246, 0.1);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* Loading Spinner */
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* No Data Message */
.no-data-message {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

.no-data {
  text-align: center;
  padding: var(--spacing-md);
  color: var(--text-muted);
  font-size: 0.9rem;
}

/* Tabs */
.tabs {
  display: flex;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.tab {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover {
  background: var(--bg-hover);
}

.tab.active {
  background: var(--color-primary);
  color: white;
}

.tab-count {
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
}

/* Content */
.history-content {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-md);
}

/* Events Tab */
.events-tab {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.filters-panel {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  flex-wrap: wrap;
  padding: var(--spacing-md);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.search-box {
  flex: 1;
  min-width: 200px;
}

.search-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.filter-group label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.filter-select {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.85rem;
}

/* Date Range Filter */
.date-range-group {
  flex-wrap: wrap;
}

.date-range-inputs {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.date-input {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.85rem;
  width: 140px;
}

.date-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.date-separator {
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* Stats Cards */
.stats-cards {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.stat-card {
  padding: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  min-width: 100px;
}

.stat-card .stat-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
  text-transform: capitalize;
}

.stat-card .stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* Events Table */
.events-table-container {
  overflow: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.events-table {
  width: 100%;
  border-collapse: collapse;
}

.events-table th,
.events-table td {
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.events-table th {
  background: var(--bg-input);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.events-table tbody tr {
  cursor: pointer;
  transition: background var(--transition-fast);
}

.events-table tbody tr:hover {
  background: var(--bg-hover);
}

.timestamp {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.category-badge {
  font-size: 0.8rem;
  text-transform: capitalize;
}

.severity-badge {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.source {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.message {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tags {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.tag {
  padding: 2px 6px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  color: var(--text-secondary);
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
}

.page-info {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* Simulations Tab */
.simulations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: var(--spacing-md);
}

.simulation-card {
  padding: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.simulation-card.failed {
  border-color: var(--color-danger);
}

.simulation-card.aborted {
  border-color: var(--color-warning);
}

.sim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.sim-header h4 {
  margin: 0;
  font-size: 1rem;
}

.sim-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.sim-time {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.time-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
}

.time-item .label {
  color: var(--text-muted);
}

.time-item .value {
  font-family: monospace;
}

.sim-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.sim-stat {
  text-align: center;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.sim-stat.detected { background: rgba(59, 130, 246, 0.1); }
.sim-stat.blocked { background: rgba(34, 197, 94, 0.1); }
.sim-stat.compromised { background: rgba(239, 68, 68, 0.1); }

.sim-stat .stat-num {
  display: block;
  font-size: 1.25rem;
  font-weight: 700;
}

.sim-stat .stat-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.sim-configs {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.config-item {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Analytics Tab */
.analytics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.analytics-card {
  padding: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.analytics-card h4 {
  margin: 0 0 var(--spacing-md);
  font-size: 0.9rem;
}

.timeline-card {
  grid-column: span 2;
}

.severity-bars {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.severity-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.bar-label {
  width: 60px;
  font-size: 0.75rem;
  text-transform: capitalize;
  color: var(--text-secondary);
}

.bar-track {
  flex: 1;
  height: 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.bar-value {
  width: 40px;
  text-align: right;
  font-size: 0.75rem;
  font-weight: 600;
}

.category-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.cat-icon {
  font-size: 1rem;
}

.cat-name {
  width: 80px;
  font-size: 0.8rem;
  text-transform: capitalize;
}

.cat-count {
  width: 40px;
  font-size: 0.75rem;
  font-weight: 600;
}

.cat-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.cat-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-full);
}

.timeline-chart {
  height: 150px;
}

.timeline-svg {
  width: 100%;
  height: 100%;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.summary-item {
  text-align: center;
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.sum-label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.sum-value {
  font-size: 1.5rem;
  font-weight: 700;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--text-muted);
  cursor: pointer;
}

.modal-body {
  padding: var(--spacing-md);
  overflow-y: auto;
  max-height: 60vh;
}

.detail-row {
  display: flex;
  margin-bottom: var(--spacing-sm);
}

.detail-label {
  width: 100px;
  font-size: 0.8rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.detail-value {
  flex: 1;
  font-size: 0.9rem;
}

.detail-value.mono {
  font-family: monospace;
  font-size: 0.8rem;
}

.detail-json {
  background: var(--bg-input);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-family: monospace;
  font-size: 0.75rem;
  overflow-x: auto;
}

/* Responsive */
@media (max-width: 1200px) {
  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .timeline-card {
    grid-column: span 1;
  }
}

@media (max-width: 768px) {
  .filters-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .simulations-grid {
    grid-template-columns: 1fr;
  }

  .sim-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>