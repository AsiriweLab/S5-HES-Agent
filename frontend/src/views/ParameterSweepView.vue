<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  sweepsApi,
  type SweepSummary,
  type SweepProgress,
  type SweepResults,
  type ParameterDefinition,
  type CreateSweepRequest,
  type TestResult,
  type DescriptiveStats,
} from '@/services/sweepsApi'

// =============================================================================
// State
// =============================================================================

// Tabs
const activeTab = ref<'sweeps' | 'create' | 'statistics'>('sweeps')

// Sweep List
const sweeps = ref<SweepSummary[]>([])
const selectedSweep = ref<SweepResults | null>(null)
const sweepProgress = ref<SweepProgress | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)

// Create Sweep Form
const newSweep = ref<CreateSweepRequest>({
  name: '',
  description: '',
  base_config: {},
  parameters: [],
  parallel_workers: 4,
  repetitions: 1,
  tags: [],
})

const newParameter = ref<ParameterDefinition>({
  name: '',
  param_type: 'discrete',
  values: [],
  description: '',
})

// Statistics
const statsData = ref<{
  group1: number[]
  group2: number[]
  allGroups: number[][]
}>({
  group1: [],
  group2: [],
  allGroups: [],
})
const statsResult = ref<TestResult | null>(null)
const descriptiveResult = ref<DescriptiveStats | null>(null)
const selectedTest = ref<string>('t-test')

// Polling
let pollInterval: ReturnType<typeof setInterval> | null = null

// =============================================================================
// Computed
// =============================================================================

const totalExperiments = computed(() => {
  if (newSweep.value.parameters.length === 0) return 0
  const counts = newSweep.value.parameters.map(p => {
    if (p.param_type === 'discrete') return p.values.length
    if (p.steps) return p.steps
    return p.values.length
  })
  return counts.reduce((a, b) => a * b, 1) * (newSweep.value.repetitions ?? 1)
})

const canCreateSweep = computed(() => {
  return newSweep.value.name.trim() !== '' && newSweep.value.parameters.length > 0
})

// =============================================================================
// Methods - Sweep Management
// =============================================================================

async function loadSweeps() {
  isLoading.value = true
  error.value = null
  try {
    const result = await sweepsApi.listSweeps()
    sweeps.value = result.sweeps
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load sweeps'
  } finally {
    isLoading.value = false
  }
}

async function selectSweep(sweepId: string) {
  isLoading.value = true
  try {
    selectedSweep.value = await sweepsApi.getSweep(sweepId)
    sweepProgress.value = await sweepsApi.getSweepProgress(sweepId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load sweep'
  } finally {
    isLoading.value = false
  }
}

async function createSweep() {
  if (!canCreateSweep.value) return

  isLoading.value = true
  error.value = null
  try {
    const result = await sweepsApi.createSweep(newSweep.value)
    await loadSweeps()

    // Reset form
    newSweep.value = {
      name: '',
      description: '',
      base_config: {},
      parameters: [],
      parallel_workers: 4,
      repetitions: 1,
      tags: [],
    }

    // Switch to sweep list and select the new sweep
    activeTab.value = 'sweeps'
    await selectSweep(result.sweep_id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create sweep'
  } finally {
    isLoading.value = false
  }
}

async function startSweep(sweepId: string) {
  try {
    await sweepsApi.startSweep(sweepId)
    // Start polling for progress
    startPolling(sweepId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to start sweep'
  }
}

async function pauseSweep(sweepId: string) {
  try {
    await sweepsApi.pauseSweep(sweepId)
    stopPolling()
    await selectSweep(sweepId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to pause sweep'
  }
}

async function cancelSweep(sweepId: string) {
  try {
    await sweepsApi.cancelSweep(sweepId)
    stopPolling()
    await selectSweep(sweepId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to cancel sweep'
  }
}

async function deleteSweep(sweepId: string) {
  if (!confirm('Are you sure you want to delete this sweep?')) return

  try {
    await sweepsApi.deleteSweep(sweepId)
    selectedSweep.value = null
    await loadSweeps()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete sweep'
  }
}

async function exportSweep(sweepId: string, format: 'json' | 'csv') {
  try {
    const result = await sweepsApi.exportSweep(sweepId, format)
    const blob = new Blob([result.data], { type: format === 'json' ? 'application/json' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sweep-${sweepId}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to export sweep'
  }
}

function startPolling(sweepId: string) {
  stopPolling()
  pollInterval = setInterval(async () => {
    try {
      sweepProgress.value = await sweepsApi.getSweepProgress(sweepId)
      if (sweepProgress.value.status === 'completed' || sweepProgress.value.status === 'failed') {
        stopPolling()
        await selectSweep(sweepId)
        await loadSweeps()
      }
    } catch {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

// =============================================================================
// Methods - Parameter Definition
// =============================================================================

function addParameter() {
  if (!newParameter.value.name.trim()) return

  const param: ParameterDefinition = { ...newParameter.value }

  // Parse values if discrete
  if (param.param_type === 'discrete' && typeof param.values === 'string') {
    param.values = (param.values as unknown as string).split(',').map(v => {
      const trimmed = v.trim()
      const num = Number(trimmed)
      return isNaN(num) ? trimmed : num
    })
  }

  newSweep.value.parameters.push(param)

  // Reset form
  newParameter.value = {
    name: '',
    param_type: 'discrete',
    values: [],
    description: '',
  }
}

function removeParameter(index: number) {
  newSweep.value.parameters.splice(index, 1)
}

// =============================================================================
// Methods - Statistics
// =============================================================================

function parseDataInput(input: string): number[] {
  return input.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
}

async function runStatisticalTest() {
  statsResult.value = null
  descriptiveResult.value = null

  try {
    if (selectedTest.value === 'descriptive') {
      descriptiveResult.value = await sweepsApi.descriptiveStats(statsData.value.group1)
    } else if (selectedTest.value === 't-test') {
      statsResult.value = await sweepsApi.tTest(statsData.value.group1, statsData.value.group2)
    } else if (selectedTest.value === 't-test-paired') {
      statsResult.value = await sweepsApi.tTest(statsData.value.group1, statsData.value.group2, { paired: true })
    } else if (selectedTest.value === 'mann-whitney') {
      statsResult.value = await sweepsApi.mannWhitney(statsData.value.group1, statsData.value.group2)
    } else if (selectedTest.value === 'anova') {
      statsResult.value = await sweepsApi.anova(statsData.value.allGroups)
    } else if (selectedTest.value === 'kruskal-wallis') {
      statsResult.value = await sweepsApi.kruskalWallis(statsData.value.allGroups)
    } else if (selectedTest.value === 'correlation') {
      statsResult.value = await sweepsApi.correlation(statsData.value.group1, statsData.value.group2)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to run test'
  }
}

// =============================================================================
// Formatting Helpers
// =============================================================================

function formatStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'var(--color-success)'
    case 'running': return 'var(--color-primary)'
    case 'paused': return 'var(--color-warning)'
    case 'failed': return 'var(--color-danger)'
    case 'cancelled': return 'var(--text-muted)'
    default: return 'var(--text-secondary)'
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

// =============================================================================
// Lifecycle
// =============================================================================

onMounted(() => {
  loadSweeps()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="sweep-view">
    <!-- Header -->
    <header class="sweep-header">
      <div class="header-left">
        <h2>Parameter Sweep & Statistics</h2>
        <span class="subtitle">Automate research experiments</span>
      </div>
      <div class="header-right">
        <button class="btn btn-ghost" @click="loadSweeps" :disabled="isLoading">
          Refresh
        </button>
      </div>
    </header>

    <!-- Error Banner -->
    <div v-if="error" class="error-banner">
      <span>{{ error }}</span>
      <button class="btn btn-ghost btn-sm" @click="error = null">Dismiss</button>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'sweeps' }"
        @click="activeTab = 'sweeps'"
      >
        Sweeps
        <span class="tab-count">{{ sweeps.length }}</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'create' }"
        @click="activeTab = 'create'"
      >
        Create Sweep
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'statistics' }"
        @click="activeTab = 'statistics'"
      >
        Statistical Tests
      </button>
    </div>

    <!-- Content -->
    <div class="sweep-content">
      <!-- Loading -->
      <div v-if="isLoading" class="loading">Loading...</div>

      <!-- Sweeps Tab -->
      <div v-else-if="activeTab === 'sweeps'" class="sweeps-tab">
        <div class="sweep-layout">
          <!-- Sweep List -->
          <div class="sweep-list">
            <h3>Parameter Sweeps</h3>
            <div v-if="sweeps.length === 0" class="empty-state">
              No sweeps yet. Create one to get started.
            </div>
            <div
              v-for="sweep in sweeps"
              :key="sweep.sweep_id"
              class="sweep-item"
              :class="{ selected: selectedSweep?.sweep_id === sweep.sweep_id }"
              @click="selectSweep(sweep.sweep_id)"
            >
              <div class="sweep-item-header">
                <span class="sweep-name">{{ sweep.name }}</span>
                <span class="sweep-status" :style="{ color: getStatusColor(sweep.status) }">
                  {{ formatStatus(sweep.status) }}
                </span>
              </div>
              <div class="sweep-item-meta">
                <span>{{ sweep.completed_experiments }}/{{ sweep.total_experiments }} experiments</span>
                <span>{{ formatDate(sweep.created_at) }}</span>
              </div>
            </div>
          </div>

          <!-- Sweep Details -->
          <div class="sweep-details">
            <div v-if="!selectedSweep" class="empty-state">
              Select a sweep to view details
            </div>
            <template v-else>
              <div class="details-header">
                <h3>{{ selectedSweep.configuration.name }}</h3>
                <div class="details-actions">
                  <button
                    v-if="selectedSweep.status === 'pending' || selectedSweep.status === 'paused'"
                    class="btn btn-primary btn-sm"
                    @click="startSweep(selectedSweep.sweep_id)"
                  >
                    Start
                  </button>
                  <button
                    v-if="selectedSweep.status === 'running'"
                    class="btn btn-warning btn-sm"
                    @click="pauseSweep(selectedSweep.sweep_id)"
                  >
                    Pause
                  </button>
                  <button
                    v-if="selectedSweep.status === 'running' || selectedSweep.status === 'paused'"
                    class="btn btn-ghost btn-sm"
                    @click="cancelSweep(selectedSweep.sweep_id)"
                  >
                    Cancel
                  </button>
                  <button
                    class="btn btn-ghost btn-sm"
                    @click="exportSweep(selectedSweep.sweep_id, 'json')"
                  >
                    Export JSON
                  </button>
                  <button
                    class="btn btn-ghost btn-sm"
                    @click="exportSweep(selectedSweep.sweep_id, 'csv')"
                  >
                    Export CSV
                  </button>
                  <button
                    class="btn btn-danger btn-sm"
                    @click="deleteSweep(selectedSweep.sweep_id)"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <!-- Progress -->
              <div v-if="sweepProgress" class="progress-section">
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    :style="{ width: `${sweepProgress.progress_percent}%` }"
                  ></div>
                </div>
                <div class="progress-stats">
                  <span>{{ sweepProgress.completed_experiments }} completed</span>
                  <span>{{ sweepProgress.running_experiments }} running</span>
                  <span>{{ sweepProgress.pending_experiments }} pending</span>
                  <span v-if="sweepProgress.failed_experiments > 0" class="failed">
                    {{ sweepProgress.failed_experiments }} failed
                  </span>
                </div>
              </div>

              <!-- Parameters -->
              <div class="section">
                <h4>Parameters</h4>
                <div class="params-grid">
                  <div
                    v-for="param in selectedSweep.configuration.parameters"
                    :key="param.name"
                    class="param-card"
                  >
                    <div class="param-name">{{ param.name }}</div>
                    <div class="param-type">{{ param.param_type }}</div>
                    <div class="param-values">
                      {{ Array.isArray(param.values) ? param.values.join(', ') : `${param.start} - ${param.end} (${param.steps} steps)` }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- Summary Statistics -->
              <div v-if="Object.keys(selectedSweep.summary_statistics).length > 0" class="section">
                <h4>Summary Statistics</h4>
                <div class="stats-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Mean</th>
                        <th>Std Dev</th>
                        <th>Min</th>
                        <th>Max</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(stats, metric) in selectedSweep.summary_statistics" :key="metric">
                        <td>{{ metric }}</td>
                        <td>{{ (stats as any).mean?.toFixed(3) }}</td>
                        <td>{{ (stats as any).std_dev?.toFixed(3) }}</td>
                        <td>{{ (stats as any).min?.toFixed(3) }}</td>
                        <td>{{ (stats as any).max?.toFixed(3) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Experiments -->
              <div class="section">
                <h4>Experiments ({{ selectedSweep.experiments.length }})</h4>
                <div class="experiments-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Parameters</th>
                        <th>Events</th>
                        <th>Detected</th>
                        <th>Blocked</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="exp in selectedSweep.experiments.slice(0, 50)"
                        :key="exp.experiment_id"
                      >
                        <td>
                          <span class="status-badge" :style="{ color: getStatusColor(exp.status) }">
                            {{ formatStatus(exp.status) }}
                          </span>
                        </td>
                        <td class="params-cell">
                          <span v-for="(val, key) in exp.parameter_values" :key="key" class="param-tag">
                            {{ key }}: {{ val }}
                          </span>
                        </td>
                        <td>{{ exp.events_count }}</td>
                        <td>{{ exp.threats_detected }}</td>
                        <td>{{ exp.threats_blocked }}</td>
                        <td>{{ exp.duration_seconds ? formatDuration(exp.duration_seconds) : '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-if="selectedSweep.experiments.length > 50" class="table-note">
                    Showing first 50 of {{ selectedSweep.experiments.length }} experiments
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Create Sweep Tab -->
      <div v-else-if="activeTab === 'create'" class="create-tab">
        <div class="create-form">
          <h3>Create Parameter Sweep</h3>

          <!-- Basic Info -->
          <div class="form-section">
            <h4>Basic Information</h4>
            <div class="form-row">
              <label>Name *</label>
              <input v-model="newSweep.name" type="text" placeholder="e.g., Threat Severity Analysis" />
            </div>
            <div class="form-row">
              <label>Description</label>
              <textarea v-model="newSweep.description" placeholder="Describe this sweep..." rows="3"></textarea>
            </div>
            <div class="form-row">
              <label>Parallel Workers</label>
              <input v-model.number="newSweep.parallel_workers" type="number" min="1" max="16" />
            </div>
            <div class="form-row">
              <label>Repetitions</label>
              <input v-model.number="newSweep.repetitions" type="number" min="1" max="100" />
            </div>
          </div>

          <!-- Parameters -->
          <div class="form-section">
            <h4>Parameters</h4>
            <div class="params-list">
              <div v-for="(param, idx) in newSweep.parameters" :key="idx" class="param-item">
                <span class="param-info">
                  <strong>{{ param.name }}</strong>
                  ({{ param.param_type }}):
                  {{ Array.isArray(param.values) ? param.values.join(', ') : `${param.start}-${param.end}` }}
                </span>
                <button class="btn btn-ghost btn-sm" @click="removeParameter(idx)">Remove</button>
              </div>
            </div>

            <!-- Add Parameter Form -->
            <div class="add-param-form">
              <div class="form-row">
                <label>Parameter Name</label>
                <input v-model="newParameter.name" type="text" placeholder="e.g., threat_severity" />
              </div>
              <div class="form-row">
                <label>Type</label>
                <select v-model="newParameter.param_type">
                  <option value="discrete">Discrete Values</option>
                  <option value="range">Range</option>
                  <option value="linspace">Linear Space</option>
                  <option value="logspace">Log Space</option>
                </select>
              </div>
              <div v-if="newParameter.param_type === 'discrete'" class="form-row">
                <label>Values (comma-separated)</label>
                <input v-model="(newParameter.values as any)" type="text" placeholder="low, medium, high" />
              </div>
              <template v-else>
                <div class="form-row">
                  <label>Start</label>
                  <input v-model.number="newParameter.start" type="number" />
                </div>
                <div class="form-row">
                  <label>End</label>
                  <input v-model.number="newParameter.end" type="number" />
                </div>
                <div class="form-row">
                  <label>Steps</label>
                  <input v-model.number="newParameter.steps" type="number" min="2" />
                </div>
              </template>
              <button class="btn btn-secondary" @click="addParameter" :disabled="!newParameter.name">
                Add Parameter
              </button>
            </div>
          </div>

          <!-- Summary -->
          <div class="form-summary">
            <p>
              Total experiments: <strong>{{ totalExperiments }}</strong>
              <span v-if="totalExperiments > 0">
                ({{ newSweep.parameters.length }} parameters x {{ newSweep.repetitions }} repetitions)
              </span>
            </p>
          </div>

          <!-- Actions -->
          <div class="form-actions">
            <button class="btn btn-primary" @click="createSweep" :disabled="!canCreateSweep">
              Create Sweep
            </button>
          </div>
        </div>
      </div>

      <!-- Statistics Tab -->
      <div v-else-if="activeTab === 'statistics'" class="statistics-tab">
        <div class="stats-layout">
          <!-- Input Section -->
          <div class="stats-input">
            <h3>Statistical Testing</h3>

            <div class="form-row">
              <label>Test Type</label>
              <select v-model="selectedTest">
                <option value="descriptive">Descriptive Statistics</option>
                <option value="t-test">Independent T-Test</option>
                <option value="t-test-paired">Paired T-Test</option>
                <option value="mann-whitney">Mann-Whitney U</option>
                <option value="anova">One-Way ANOVA</option>
                <option value="kruskal-wallis">Kruskal-Wallis H</option>
                <option value="correlation">Pearson Correlation</option>
              </select>
            </div>

            <div class="form-row">
              <label>Group 1 Data (comma-separated)</label>
              <textarea
                :value="statsData.group1.join(', ')"
                @input="statsData.group1 = parseDataInput(($event.target as HTMLTextAreaElement).value)"
                placeholder="e.g., 23.5, 25.1, 22.8, 24.3"
                rows="3"
              ></textarea>
            </div>

            <div v-if="selectedTest !== 'descriptive'" class="form-row">
              <label>Group 2 Data (comma-separated)</label>
              <textarea
                :value="statsData.group2.join(', ')"
                @input="statsData.group2 = parseDataInput(($event.target as HTMLTextAreaElement).value)"
                placeholder="e.g., 26.1, 27.3, 25.9, 28.2"
                rows="3"
              ></textarea>
            </div>

            <button class="btn btn-primary" @click="runStatisticalTest">
              Run Test
            </button>
          </div>

          <!-- Results Section -->
          <div class="stats-results">
            <h3>Results</h3>

            <div v-if="!statsResult && !descriptiveResult" class="empty-state">
              Enter data and run a test to see results
            </div>

            <!-- Descriptive Stats Results -->
            <div v-else-if="descriptiveResult" class="results-card">
              <h4>Descriptive Statistics</h4>
              <div class="result-grid">
                <div class="result-item">
                  <span class="label">N</span>
                  <span class="value">{{ descriptiveResult.n }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Mean</span>
                  <span class="value">{{ descriptiveResult.mean.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Median</span>
                  <span class="value">{{ descriptiveResult.median.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Std Dev</span>
                  <span class="value">{{ descriptiveResult.std_dev.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Std Error</span>
                  <span class="value">{{ descriptiveResult.std_error.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Min</span>
                  <span class="value">{{ descriptiveResult.min_val.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">Max</span>
                  <span class="value">{{ descriptiveResult.max_val.toFixed(4) }}</span>
                </div>
                <div class="result-item">
                  <span class="label">IQR</span>
                  <span class="value">{{ descriptiveResult.iqr.toFixed(4) }}</span>
                </div>
              </div>
            </div>

            <!-- Test Results -->
            <div v-else-if="statsResult" class="results-card">
              <h4>{{ statsResult.test_type.replace(/_/g, ' ').toUpperCase() }}</h4>

              <div class="result-grid">
                <div class="result-item">
                  <span class="label">Test Statistic</span>
                  <span class="value">{{ statsResult.test_statistic.toFixed(4) }}</span>
                </div>
                <div class="result-item highlight">
                  <span class="label">p-value</span>
                  <span class="value" :class="{ significant: statsResult.is_significant }">
                    {{ statsResult.p_value.toFixed(4) }}
                  </span>
                </div>
                <div v-if="statsResult.degrees_of_freedom" class="result-item">
                  <span class="label">Degrees of Freedom</span>
                  <span class="value">{{ statsResult.degrees_of_freedom.toFixed(2) }}</span>
                </div>
                <div v-if="statsResult.effect_size" class="result-item">
                  <span class="label">Effect Size ({{ statsResult.effect_size_type }})</span>
                  <span class="value">{{ statsResult.effect_size.toFixed(4) }}</span>
                </div>
              </div>

              <div class="significance-badge" :class="{ significant: statsResult.is_significant }">
                {{ statsResult.is_significant ? 'Statistically Significant' : 'Not Significant' }}
                (α = {{ statsResult.alpha }})
              </div>

              <div class="interpretation">
                {{ statsResult.interpretation }}
              </div>

              <div v-if="statsResult.confidence_interval" class="confidence-interval">
                {{ (statsResult.confidence_level * 100).toFixed(0) }}% CI:
                [{{ statsResult.confidence_interval[0].toFixed(4) }}, {{ statsResult.confidence_interval[1].toFixed(4) }}]
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sweep-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Header */
.sweep-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left h2 {
  margin: 0;
  font-size: 1.25rem;
}

.header-left .subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* Error Banner */
.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-lg);
  background: rgba(239, 68, 68, 0.1);
  border-bottom: 1px solid var(--color-danger);
  color: var(--color-danger);
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
.sweep-content {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-md);
}

.loading {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

/* Sweeps Tab */
.sweep-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--spacing-md);
  height: 100%;
}

.sweep-list {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  overflow-y: auto;
}

.sweep-list h3 {
  margin: 0 0 var(--spacing-md);
  font-size: 1rem;
}

.sweep-item {
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sweep-item:hover {
  background: var(--bg-hover);
}

.sweep-item.selected {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.1);
}

.sweep-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.sweep-name {
  font-weight: 500;
}

.sweep-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.sweep-item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Sweep Details */
.sweep-details {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  overflow-y: auto;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.details-header h3 {
  margin: 0;
}

.details-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.progress-section {
  margin-bottom: var(--spacing-md);
}

.progress-bar {
  height: 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--spacing-xs);
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.3s ease;
}

.progress-stats {
  display: flex;
  gap: var(--spacing-md);
  font-size: 0.8rem;
  color: var(--text-muted);
}

.progress-stats .failed {
  color: var(--color-danger);
}

.section {
  margin-bottom: var(--spacing-lg);
}

.section h4 {
  margin: 0 0 var(--spacing-sm);
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-sm);
}

.param-card {
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.param-name {
  font-weight: 500;
  margin-bottom: 2px;
}

.param-type {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.param-values {
  font-size: 0.85rem;
  font-family: monospace;
}

/* Tables */
.stats-table,
.experiments-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

th, td {
  padding: var(--spacing-sm);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

th {
  background: var(--bg-input);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.status-badge {
  font-weight: 600;
  font-size: 0.75rem;
}

.params-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.param-tag {
  padding: 2px 6px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-family: monospace;
}

.table-note {
  padding: var(--spacing-sm);
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* Create Tab */
.create-form {
  max-width: 800px;
  margin: 0 auto;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
}

.create-form h3 {
  margin: 0 0 var(--spacing-lg);
}

.form-section {
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.form-section h4 {
  margin: 0 0 var(--spacing-md);
  font-size: 0.9rem;
}

.form-row {
  margin-bottom: var(--spacing-md);
}

.form-row label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.form-row input,
.form-row textarea,
.form-row select {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.params-list {
  margin-bottom: var(--spacing-md);
}

.param-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-xs);
}

.add-param-form {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.form-summary {
  text-align: center;
  margin-bottom: var(--spacing-md);
  color: var(--text-secondary);
}

.form-summary strong {
  color: var(--text-primary);
  font-size: 1.25rem;
}

.form-actions {
  display: flex;
  justify-content: center;
}

/* Statistics Tab */
.stats-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  height: 100%;
}

.stats-input,
.stats-results {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
}

.stats-input h3,
.stats-results h3 {
  margin: 0 0 var(--spacing-md);
  font-size: 1rem;
}

.results-card {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.results-card h4 {
  margin: 0 0 var(--spacing-md);
  font-size: 0.9rem;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.result-item {
  padding: var(--spacing-sm);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.result-item .label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.result-item .value {
  font-size: 1.1rem;
  font-weight: 600;
  font-family: monospace;
}

.result-item .value.significant {
  color: var(--color-success);
}

.result-item.highlight {
  background: rgba(59, 130, 246, 0.1);
}

.significance-badge {
  display: inline-block;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: var(--spacing-sm);
}

.significance-badge.significant {
  background: rgba(34, 197, 94, 0.2);
  color: var(--color-success);
}

.interpretation {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.confidence-interval {
  font-size: 0.85rem;
  font-family: monospace;
  color: var(--text-muted);
}

/* Button styles */
.btn {
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-warning {
  background: var(--color-warning);
  color: #000;
}

.btn-danger {
  background: var(--color-danger);
  color: white;
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background: var(--bg-hover);
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.8rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 1200px) {
  .sweep-layout,
  .stats-layout {
    grid-template-columns: 1fr;
  }

  .sweep-list {
    max-height: 200px;
  }
}
</style>
