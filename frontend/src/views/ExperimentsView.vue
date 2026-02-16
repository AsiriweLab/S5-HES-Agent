<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  experimentsApi,
  formatVersion,
  formatDate,
  type Experiment,
  type ExperimentVersion,
  type VersionComparison,
  type ExperimentStats,
} from '@/services/experimentsApi'

// State
const experiments = ref<Experiment[]>([])
const selectedExperiment = ref<Experiment | null>(null)
const selectedVersion = ref<ExperimentVersion | null>(null)
const versionLog = ref<ExperimentVersion[]>([])
const stats = ref<ExperimentStats | null>(null)
const comparison = ref<VersionComparison | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)

// Filters
const statusFilter = ref<string>('')

// Modal state
const showImportModal = ref(false)
const showCommitModal = ref(false)
const showDiffModal = ref(false)
const compareVersionA = ref<string>('')
const compareVersionB = ref<string>('')

// Import experiment state
const jsonFileInput = ref<HTMLInputElement | null>(null)
const importedExperiment = ref<{
  name: string
  description?: string
  category?: string
  tags: string[]
  status: string
  versions: any[]
  config_snapshot?: any
  // For simulation results imports
  isSimulationResult?: boolean
  simulationData?: {
    simulationId: string
    completedAt: string
    duration: number
    homeConfig: any
    threatScenario: any
    statistics: any
    eventLog: any[]
  }
} | null>(null)
const jsonFileName = ref<string>('')
const isImporting = ref(false)

const commitForm = ref({
  message: '',
  version_type: 'patch' as 'major' | 'minor' | 'patch',
  notes: '',
  research_question: '',
  hypothesis: '',
})

// Computed
const filteredExperiments = computed(() => {
  let result = experiments.value
  if (statusFilter.value) {
    result = result.filter((e) => e.status === statusFilter.value)
  }
  return result
})

const currentVersion = computed(() => {
  if (!selectedExperiment.value) return null
  return selectedExperiment.value.versions.find(
    (v) => v.version_id === selectedExperiment.value?.current_version_id
  )
})

// Methods
async function loadExperiments() {
  isLoading.value = true
  error.value = null
  try {
    const result = await experimentsApi.listExperiments()
    experiments.value = result.experiments
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load experiments'
  } finally {
    isLoading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await experimentsApi.getStats()
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

async function selectExperiment(experiment: Experiment) {
  selectedExperiment.value = experiment
  selectedVersion.value = null
  comparison.value = null
  await loadVersionLog(experiment.experiment_id)
}

async function loadVersionLog(experimentId: string) {
  try {
    const result = await experimentsApi.getVersionLog(experimentId)
    versionLog.value = result.versions
  } catch (e) {
    console.error('Failed to load version log:', e)
  }
}

function selectVersion(version: ExperimentVersion) {
  selectedVersion.value = version
  comparison.value = null
}

function openImportModal() {
  showImportModal.value = true
  importedExperiment.value = null
  jsonFileName.value = ''
}

function triggerJsonFileInput() {
  jsonFileInput.value?.click()
}

function handleExperimentFileLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  jsonFileName.value = file.name

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const data = JSON.parse(content)

      // Check if it's a simulation results export (has simulationId and homeConfig)
      if (data.simulationId && data.homeConfig) {
        // Convert simulation results to experiment format
        const simulationMode = data.threatScenario ? 'threat' : 'benign'
        const experimentName = `Simulation ${data.simulationId.slice(0, 8)} (${simulationMode})`

        importedExperiment.value = {
          name: experimentName,
          description: `Imported from simulation completed at ${data.completedAt}`,
          category: 'simulation-import',
          tags: ['imported', 'simulation-results', simulationMode],
          status: 'completed',
          versions: [], // Will be created on import
          isSimulationResult: true,
          simulationData: {
            simulationId: data.simulationId,
            completedAt: data.completedAt,
            duration: data.duration,
            homeConfig: data.homeConfig,
            threatScenario: data.threatScenario,
            statistics: data.statistics,
            eventLog: data.eventLog || [],
          },
        }
        return
      }

      // Validate it's an experiment file (has experiment structure)
      if (!data.name || !data.versions || !Array.isArray(data.versions)) {
        alert('Invalid file format. Please select an exported experiment or simulation results JSON file.')
        importedExperiment.value = null
        jsonFileName.value = ''
        return
      }

      importedExperiment.value = {
        name: data.name,
        description: data.description,
        category: data.category,
        tags: data.tags || [],
        status: data.status || 'completed',
        versions: data.versions,
        config_snapshot: data.versions?.[0]?.config_snapshot,
      }
    } catch (err) {
      console.error('Failed to parse JSON file:', err)
      alert('Failed to load file: Invalid JSON format')
      importedExperiment.value = null
      jsonFileName.value = ''
    }
  }
  reader.readAsText(file)

  // Reset input to allow loading the same file again
  input.value = ''
}

function clearImportedExperiment() {
  importedExperiment.value = null
  jsonFileName.value = ''
}

async function importExperiment() {
  if (!importedExperiment.value) {
    alert('Please select an experiment file to import')
    return
  }

  isImporting.value = true
  try {
    let created: Experiment

    // Check if it's a simulation results import
    if (importedExperiment.value.isSimulationResult && importedExperiment.value.simulationData) {
      const simData = importedExperiment.value.simulationData
      const simulationMode = simData.threatScenario ? 'threat' : 'benign'

      // Use the /from-simulation endpoint for simulation results
      created = await experimentsApi.saveFromSimulation({
        name: importedExperiment.value.name,
        description: importedExperiment.value.description,
        category: importedExperiment.value.category || 'simulation-import',
        tags: importedExperiment.value.tags,
        simulation_id: simData.simulationId,
        completed_at: simData.completedAt,
        duration_minutes: Math.round(simData.duration / 60),
        simulation_mode: simulationMode,
        home_config: simData.homeConfig,
        threat_scenario: simData.threatScenario,
        statistics: simData.statistics,
        event_log: simData.eventLog,
      })
    } else {
      // Regular experiment import
      const configSnapshot = importedExperiment.value.config_snapshot || {
        home_config: {},
        simulation_params: {},
        threat_scenarios: [],
        behavior_config: {},
      }

      created = await experimentsApi.createExperiment({
        name: importedExperiment.value.name,
        description: importedExperiment.value.description || undefined,
        category: importedExperiment.value.category || 'imported',
        tags: [...(importedExperiment.value.tags || []), 'imported'],
        initial_config: configSnapshot,
      })
    }

    experiments.value.unshift(created)
    showImportModal.value = false
    importedExperiment.value = null
    jsonFileName.value = ''
    await selectExperiment(created)
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to import experiment')
  } finally {
    isImporting.value = false
  }
}

async function commitVersion() {
  if (!selectedExperiment.value || !commitForm.value.message.trim()) {
    alert('Please enter a commit message')
    return
  }

  isLoading.value = true
  try {
    const newVersion = await experimentsApi.commit(selectedExperiment.value.experiment_id, {
      message: commitForm.value.message,
      version_type: commitForm.value.version_type,
      notes: commitForm.value.notes || undefined,
      research_question: commitForm.value.research_question || undefined,
      hypothesis: commitForm.value.hypothesis || undefined,
    })

    // Refresh experiment
    const updated = await experimentsApi.getExperiment(selectedExperiment.value.experiment_id)
    selectedExperiment.value = updated
    await loadVersionLog(updated.experiment_id)
    selectVersion(newVersion)

    showCommitModal.value = false
    commitForm.value = {
      message: '',
      version_type: 'patch',
      notes: '',
      research_question: '',
      hypothesis: '',
    }
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to commit version')
  } finally {
    isLoading.value = false
  }
}

async function compareVersions() {
  if (!selectedExperiment.value || !compareVersionA.value || !compareVersionB.value) {
    alert('Please select two versions to compare')
    return
  }

  try {
    comparison.value = await experimentsApi.diff(
      selectedExperiment.value.experiment_id,
      compareVersionA.value,
      compareVersionB.value
    )
    showDiffModal.value = false
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to compare versions')
  }
}

async function checkoutVersion(versionId: string) {
  if (!selectedExperiment.value) return

  try {
    await experimentsApi.checkout(selectedExperiment.value.experiment_id, {
      version_id: versionId,
    })
    const updated = await experimentsApi.getExperiment(selectedExperiment.value.experiment_id)
    selectedExperiment.value = updated
    alert('Checked out version successfully')
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to checkout version')
  }
}

async function deleteExperiment(experimentId: string) {
  if (!confirm('Are you sure you want to delete this experiment?')) return

  try {
    await experimentsApi.deleteExperiment(experimentId)
    experiments.value = experiments.value.filter((e) => e.experiment_id !== experimentId)
    if (selectedExperiment.value?.experiment_id === experimentId) {
      selectedExperiment.value = null
      selectedVersion.value = null
      versionLog.value = []
    }
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to delete experiment')
  }
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    draft: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'error',
    archived: 'secondary',
  }
  return colors[status] || 'info'
}

function getDiffTypeColor(diffType: string): string {
  const colors: Record<string, string> = {
    added: '#4caf50',
    removed: '#f44336',
    modified: '#ff9800',
  }
  return colors[diffType] || '#666'
}

// Lifecycle
onMounted(async () => {
  await Promise.all([loadExperiments(), loadStats()])
})
</script>

<template>
  <div class="experiments-view">
    <div class="header">
      <h2>Experiment Version Control</h2>
      <div class="header-actions">
        <button class="btn btn-outline" @click="openImportModal">Import Experiment</button>
      </div>
    </div>

    <!-- Info Banner -->
    <div class="info-banner">
      <span class="info-icon">&#9432;</span>
      <span>Experiments are created from completed simulations. Run a simulation and click "Save as Experiment" when it completes.</span>
    </div>

    <!-- Stats Bar -->
    <div v-if="stats" class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">{{ stats.total_experiments }}</span>
        <span class="stat-label">Experiments</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ stats.total_versions }}</span>
        <span class="stat-label">Versions</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ stats.total_branches }}</span>
        <span class="stat-label">Branches</span>
      </div>
    </div>

    <!-- Main Layout -->
    <div class="main-layout">
      <!-- Experiments List -->
      <div class="panel experiments-panel">
        <div class="panel-header">
          <h3>Experiments</h3>
          <div class="filters">
            <select
              id="experiment-status-filter"
              v-model="statusFilter"
              class="filter-select"
              aria-label="Filter experiments by status"
            >
              <option value="">All Status</option>
              <option value="draft">Draft</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        <div v-if="isLoading" class="loading">Loading...</div>
        <div v-else-if="error" class="error">{{ error }}</div>
        <div v-else-if="filteredExperiments.length === 0" class="empty">
          No experiments found. Run a simulation and save it as an experiment.
        </div>
        <div v-else class="experiment-list">
          <div
            v-for="exp in filteredExperiments"
            :key="exp.experiment_id"
            :class="['experiment-item', { selected: selectedExperiment?.experiment_id === exp.experiment_id }]"
            @click="selectExperiment(exp)"
          >
            <div class="exp-header">
              <span class="exp-name">{{ exp.name }}</span>
              <span :class="['status-badge', getStatusColor(exp.status)]">{{ exp.status }}</span>
            </div>
            <div class="exp-meta">
              <span v-if="exp.category" class="category">{{ exp.category }}</span>
              <span class="versions">{{ exp.versions.length }} versions</span>
            </div>
            <div class="exp-tags" v-if="exp.tags.length">
              <span v-for="tag in exp.tags.slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
            </div>
            <div class="exp-date">{{ formatDate(exp.last_modified) }}</div>
          </div>
        </div>
      </div>

      <!-- Version History -->
      <div class="panel versions-panel" v-if="selectedExperiment">
        <div class="panel-header">
          <h3>Version History</h3>
          <div class="version-actions">
            <button class="btn btn-sm" @click="showDiffModal = true" :disabled="versionLog.length < 2">
              Compare
            </button>
            <button class="btn btn-sm btn-primary" @click="showCommitModal = true">Commit</button>
          </div>
        </div>

        <div class="branch-info">
          <span class="branch-label">Branch:</span>
          <span class="branch-name">{{ selectedExperiment.current_branch }}</span>
        </div>

        <div class="version-list">
          <div
            v-for="version in versionLog"
            :key="version.version_id"
            :class="['version-item', {
              selected: selectedVersion?.version_id === version.version_id,
              current: version.version_id === selectedExperiment.current_version_id
            }]"
            @click="selectVersion(version)"
          >
            <div class="version-header">
              <span class="version-number">{{ formatVersion(version.version) }}</span>
              <span v-if="version.version_id === selectedExperiment.current_version_id" class="current-badge">
                HEAD
              </span>
            </div>
            <div class="version-message">{{ version.commit_message }}</div>
            <div class="version-meta">
              <span class="author">{{ version.provenance.created_by }}</span>
              <span class="date">{{ formatDate(version.provenance.created_at) }}</span>
            </div>
            <div class="version-tags" v-if="version.tags.length">
              <span v-for="tag in version.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
            <div class="version-actions-inline">
              <button
                class="btn-link"
                @click.stop="checkoutVersion(version.version_id)"
                v-if="version.version_id !== selectedExperiment.current_version_id"
              >
                Checkout
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Version Details / Diff View -->
      <div class="panel details-panel" v-if="selectedExperiment">
        <!-- Comparison View -->
        <template v-if="comparison">
          <div class="panel-header">
            <h3>Version Comparison</h3>
            <button class="btn btn-sm" @click="comparison = null">Close</button>
          </div>

          <div class="diff-summary">
            <span class="diff-stat added">+{{ comparison.summary.added }} added</span>
            <span class="diff-stat removed">-{{ comparison.summary.removed }} removed</span>
            <span class="diff-stat modified">~{{ comparison.summary.modified }} modified</span>
          </div>

          <div class="diff-list">
            <div
              v-for="(diff, idx) in comparison.differences"
              :key="idx"
              :class="['diff-item', diff.diff_type]"
            >
              <div class="diff-path" :style="{ color: getDiffTypeColor(diff.diff_type) }">
                {{ diff.field_path }}
              </div>
              <div class="diff-values" v-if="diff.diff_type !== 'unchanged'">
                <div v-if="diff.old_value !== undefined" class="old-value">
                  - {{ JSON.stringify(diff.old_value) }}
                </div>
                <div v-if="diff.new_value !== undefined" class="new-value">
                  + {{ JSON.stringify(diff.new_value) }}
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Version Details -->
        <template v-else-if="selectedVersion">
          <div class="panel-header">
            <h3>Version {{ formatVersion(selectedVersion.version) }}</h3>
          </div>

          <div class="detail-section">
            <h4>Commit Info</h4>
            <div class="detail-row">
              <span class="label">Message:</span>
              <span class="value">{{ selectedVersion.commit_message }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Author:</span>
              <span class="value">{{ selectedVersion.provenance.created_by }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Date:</span>
              <span class="value">{{ formatDate(selectedVersion.provenance.created_at) }}</span>
            </div>
            <div class="detail-row" v-if="selectedVersion.notes">
              <span class="label">Notes:</span>
              <span class="value">{{ selectedVersion.notes }}</span>
            </div>
          </div>

          <div class="detail-section" v-if="selectedVersion.provenance.research_question || selectedVersion.provenance.hypothesis">
            <h4>Research Context</h4>
            <div class="detail-row" v-if="selectedVersion.provenance.research_question">
              <span class="label">Question:</span>
              <span class="value">{{ selectedVersion.provenance.research_question }}</span>
            </div>
            <div class="detail-row" v-if="selectedVersion.provenance.hypothesis">
              <span class="label">Hypothesis:</span>
              <span class="value">{{ selectedVersion.provenance.hypothesis }}</span>
            </div>
          </div>

          <div class="detail-section">
            <h4>Configuration Snapshot</h4>
            <div class="config-preview">
              <div class="config-item">
                <span class="config-label">Home Config:</span>
                <span class="config-count">
                  {{ Object.keys(selectedVersion.config_snapshot.home_config).length }} fields
                </span>
              </div>
              <div class="config-item">
                <span class="config-label">Simulation Params:</span>
                <span class="config-count">
                  {{ Object.keys(selectedVersion.config_snapshot.simulation_params).length }} fields
                </span>
              </div>
              <div class="config-item">
                <span class="config-label">Threat Scenarios:</span>
                <span class="config-count">
                  {{ selectedVersion.config_snapshot.threat_scenarios.length }} scenarios
                </span>
              </div>
            </div>
          </div>

          <div class="detail-section" v-if="selectedVersion.provenance.rag_sources.length">
            <h4>RAG Sources</h4>
            <div class="rag-sources">
              <div v-for="src in selectedVersion.provenance.rag_sources" :key="src.doc_id" class="rag-source">
                <span class="source-title">{{ src.title }}</span>
                <span class="source-score">{{ (src.relevance_score * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </template>

        <!-- Experiment Overview -->
        <template v-else>
          <div class="panel-header">
            <h3>{{ selectedExperiment.name }}</h3>
            <button class="btn btn-sm btn-danger" @click="deleteExperiment(selectedExperiment.experiment_id)">
              Delete
            </button>
          </div>

          <div class="detail-section">
            <p v-if="selectedExperiment.description">{{ selectedExperiment.description }}</p>
            <div class="detail-row">
              <span class="label">Status:</span>
              <span :class="['status-badge', getStatusColor(selectedExperiment.status)]">
                {{ selectedExperiment.status }}
              </span>
            </div>
            <div class="detail-row" v-if="selectedExperiment.category">
              <span class="label">Category:</span>
              <span class="value">{{ selectedExperiment.category }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Created:</span>
              <span class="value">{{ formatDate(selectedExperiment.created_at) }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Current Version:</span>
              <span class="value" v-if="currentVersion">{{ formatVersion(currentVersion.version) }}</span>
            </div>
          </div>

          <div class="detail-section" v-if="selectedExperiment.tags.length">
            <h4>Tags</h4>
            <div class="tags-list">
              <span v-for="tag in selectedExperiment.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>

          <!-- Simulation Results (for experiments saved from simulations) -->
          <template v-if="currentVersion && (currentVersion.config_snapshot?.research_integrity as any)?.statistics">
            <div class="detail-section simulation-results">
              <h4>Simulation Results</h4>
              <div class="sim-stats-grid">
                <div class="sim-stat">
                  <span class="sim-stat-value">{{ (currentVersion.config_snapshot?.research_integrity as any)?.statistics?.totalEvents || 0 }}</span>
                  <span class="sim-stat-label">Total Events</span>
                </div>
                <div class="sim-stat detected">
                  <span class="sim-stat-value">{{ (currentVersion.config_snapshot?.research_integrity as any)?.statistics?.detectedThreats || 0 }}</span>
                  <span class="sim-stat-label">Detected</span>
                </div>
                <div class="sim-stat blocked">
                  <span class="sim-stat-value">{{ (currentVersion.config_snapshot?.research_integrity as any)?.statistics?.blockedThreats || 0 }}</span>
                  <span class="sim-stat-label">Blocked</span>
                </div>
                <div class="sim-stat compromised">
                  <span class="sim-stat-value">{{ (currentVersion.config_snapshot?.research_integrity as any)?.statistics?.compromisedDevices || 0 }}</span>
                  <span class="sim-stat-label">Compromised</span>
                </div>
              </div>
              <div class="sim-meta" v-if="currentVersion.config_snapshot?.simulation_params">
                <div class="detail-row" v-if="(currentVersion.config_snapshot?.simulation_params as any)?.simulation_mode">
                  <span class="label">Mode:</span>
                  <span class="value mode-badge" :class="(currentVersion.config_snapshot?.simulation_params as any)?.simulation_mode">
                    {{ (currentVersion.config_snapshot?.simulation_params as any)?.simulation_mode }}
                  </span>
                </div>
                <div class="detail-row" v-if="(currentVersion.config_snapshot?.simulation_params as any)?.duration_minutes">
                  <span class="label">Duration:</span>
                  <span class="value">{{ (currentVersion.config_snapshot?.simulation_params as any)?.duration_minutes }} minutes</span>
                </div>
                <div class="detail-row" v-if="(currentVersion.config_snapshot?.simulation_params as any)?.completed_at">
                  <span class="label">Completed:</span>
                  <span class="value">{{ formatDate((currentVersion.config_snapshot?.simulation_params as any)?.completed_at) }}</span>
                </div>
              </div>
              <div class="detail-row" v-if="(currentVersion.config_snapshot?.research_integrity as any)?.event_count">
                <span class="label">Event Log:</span>
                <span class="value">{{ (currentVersion.config_snapshot?.research_integrity as any)?.event_count }} entries</span>
              </div>
            </div>
          </template>
        </template>
      </div>
    </div>

    <!-- Import Experiment Modal -->
    <div v-if="showImportModal" class="modal-overlay" @click.self="showImportModal = false">
      <div class="modal modal-lg">
        <h3>Import Experiment</h3>
        <p class="modal-description">
          Import a previously exported experiment or simulation results JSON file. This allows you to restore experiments or convert simulation exports into experiments.
        </p>

        <!-- Hidden file input -->
        <input
          ref="jsonFileInput"
          type="file"
          accept=".json"
          style="display: none"
          @change="handleExperimentFileLoad"
        />

        <div class="import-section">
          <div v-if="importedExperiment" class="file-loaded">
            <div class="file-info">
              <span class="file-icon">&#128196;</span>
              <span class="file-name">{{ jsonFileName }}</span>
              <button class="btn-icon" @click="clearImportedExperiment" title="Remove file">&#10005;</button>
            </div>
            <!-- Simulation Results Preview -->
            <div v-if="importedExperiment.isSimulationResult" class="import-preview simulation-preview">
              <div class="preview-header">
                <span class="sim-badge">Simulation Results</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Name:</span>
                <span class="preview-value">{{ importedExperiment.name }}</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Simulation ID:</span>
                <span class="preview-value mono">{{ importedExperiment.simulationData?.simulationId }}</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Completed:</span>
                <span class="preview-value">{{ formatDate(importedExperiment.simulationData?.completedAt || '') }}</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Duration:</span>
                <span class="preview-value">{{ Math.round((importedExperiment.simulationData?.duration || 0) / 60) }} minutes</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Mode:</span>
                <span class="preview-value mode-badge" :class="importedExperiment.simulationData?.threatScenario ? 'threat' : 'benign'">
                  {{ importedExperiment.simulationData?.threatScenario ? 'Threat' : 'Benign' }}
                </span>
              </div>
              <div class="sim-stats-preview" v-if="importedExperiment.simulationData?.statistics">
                <div class="mini-stat">
                  <span class="mini-stat-value">{{ importedExperiment.simulationData.statistics.totalEvents || 0 }}</span>
                  <span class="mini-stat-label">Events</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-stat-value">{{ importedExperiment.simulationData.statistics.detectedThreats || 0 }}</span>
                  <span class="mini-stat-label">Detected</span>
                </div>
                <div class="mini-stat">
                  <span class="mini-stat-value">{{ importedExperiment.simulationData.statistics.blockedThreats || 0 }}</span>
                  <span class="mini-stat-label">Blocked</span>
                </div>
              </div>
              <div class="preview-row" v-if="importedExperiment.tags.length">
                <span class="preview-label">Tags:</span>
                <span class="preview-value">{{ importedExperiment.tags.join(', ') }}</span>
              </div>
            </div>
            <!-- Regular Experiment Preview -->
            <div v-else class="import-preview">
              <div class="preview-row">
                <span class="preview-label">Name:</span>
                <span class="preview-value">{{ importedExperiment.name }}</span>
              </div>
              <div class="preview-row" v-if="importedExperiment.description">
                <span class="preview-label">Description:</span>
                <span class="preview-value">{{ importedExperiment.description }}</span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Status:</span>
                <span :class="['status-badge', getStatusColor(importedExperiment.status)]">
                  {{ importedExperiment.status }}
                </span>
              </div>
              <div class="preview-row">
                <span class="preview-label">Versions:</span>
                <span class="preview-value">{{ importedExperiment.versions.length }}</span>
              </div>
              <div class="preview-row" v-if="importedExperiment.tags.length">
                <span class="preview-label">Tags:</span>
                <span class="preview-value">{{ importedExperiment.tags.join(', ') }}</span>
              </div>
            </div>
          </div>
          <div v-else class="file-upload-area" @click="triggerJsonFileInput">
            <span class="upload-icon">&#128194;</span>
            <span>Click to select a JSON file</span>
            <span class="upload-hint">Accepts experiment exports or simulation results exports</span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn" @click="showImportModal = false">Cancel</button>
          <button
            class="btn btn-primary"
            @click="importExperiment"
            :disabled="isImporting || !importedExperiment"
          >
            {{ isImporting ? 'Importing...' : 'Import Experiment' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Commit Modal -->
    <div v-if="showCommitModal" class="modal-overlay" @click.self="showCommitModal = false">
      <div class="modal">
        <h3>Commit New Version</h3>
        <div class="form-group">
          <label for="commit-message">Commit Message *</label>
          <input id="commit-message" name="commit-message" v-model="commitForm.message" type="text" placeholder="Describe your changes" />
        </div>
        <div class="form-group">
          <label for="version-type">Version Type</label>
          <select id="version-type" name="version-type" v-model="commitForm.version_type">
            <option value="patch">Patch (bug fixes, tweaks)</option>
            <option value="minor">Minor (new features, parameters)</option>
            <option value="major">Major (breaking changes)</option>
          </select>
        </div>
        <div class="form-group">
          <label for="commit-notes">Notes</label>
          <textarea id="commit-notes" name="commit-notes" v-model="commitForm.notes" placeholder="Additional notes" rows="2"></textarea>
        </div>
        <div class="form-group">
          <label for="research-question">Research Question</label>
          <input id="research-question" name="research-question" v-model="commitForm.research_question" type="text" placeholder="What are you investigating?" />
        </div>
        <div class="form-group">
          <label for="hypothesis">Hypothesis</label>
          <input id="hypothesis" name="hypothesis" v-model="commitForm.hypothesis" type="text" placeholder="Expected outcome" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showCommitModal = false">Cancel</button>
          <button class="btn btn-primary" @click="commitVersion" :disabled="isLoading">Commit</button>
        </div>
      </div>
    </div>

    <!-- Diff Modal -->
    <div v-if="showDiffModal" class="modal-overlay" @click.self="showDiffModal = false">
      <div class="modal">
        <h3>Compare Versions</h3>
        <div class="form-group">
          <label>Version A</label>
          <select v-model="compareVersionA">
            <option value="">Select version</option>
            <option v-for="v in versionLog" :key="v.version_id" :value="v.version_id">
              {{ formatVersion(v.version) }} - {{ v.commit_message.slice(0, 30) }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>Version B</label>
          <select v-model="compareVersionB">
            <option value="">Select version</option>
            <option v-for="v in versionLog" :key="v.version_id" :value="v.version_id">
              {{ formatVersion(v.version) }} - {{ v.commit_message.slice(0, 30) }}
            </option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showDiffModal = false">Cancel</button>
          <button class="btn btn-primary" @click="compareVersions">Compare</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.experiments-view {
  padding: var(--spacing-lg);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.header h2 {
  margin: 0;
}

/* Info Banner */
.info-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(0, 217, 255, 0.1);
  border: 1px solid rgba(0, 217, 255, 0.3);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.info-icon {
  font-size: 1.25rem;
  color: var(--color-primary);
}

/* Stats Bar */
.stats-bar {
  display: flex;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-card);
  border-radius: var(--radius-md);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* Main Layout */
.main-layout {
  display: grid;
  grid-template-columns: 280px 300px 1fr;
  gap: var(--spacing-md);
  flex: 1;
  min-height: 0;
}

.panel {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--bg-input);
}

.panel-header h3 {
  margin: 0;
  font-size: 1rem;
}

/* Experiments Panel */
.experiments-panel {
  max-height: 100%;
}

.filters {
  display: flex;
  gap: var(--spacing-sm);
}

.filter-select {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--bg-input);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.75rem;
}

.experiment-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.experiment-item {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.experiment-item:hover {
  border-color: var(--color-primary);
}

.experiment-item.selected {
  border-color: var(--color-primary);
  background: rgba(0, 217, 255, 0.1);
}

.exp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.exp-name {
  font-weight: 600;
  color: var(--text-primary);
}

.exp-meta {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.exp-tags {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  margin-bottom: var(--spacing-xs);
}

.exp-date {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

/* Status Badge */
.status-badge {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.info {
  background: rgba(0, 217, 255, 0.2);
  color: #00d9ff;
}

.status-badge.warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.status-badge.success {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.status-badge.error {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.status-badge.secondary {
  background: rgba(158, 158, 158, 0.2);
  color: #9e9e9e;
}

/* Tags */
.tag {
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

/* Version Panel */
.versions-panel {
  max-height: 100%;
}

.branch-info {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  display: flex;
  gap: var(--spacing-sm);
  font-size: 0.875rem;
}

.branch-label {
  color: var(--text-secondary);
}

.branch-name {
  color: var(--color-primary);
  font-weight: 600;
}

.version-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.version-item {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  border: 2px solid transparent;
  border-left: 4px solid var(--bg-input);
  transition: all 0.2s;
}

.version-item:hover {
  border-color: var(--color-primary);
  border-left-color: var(--color-primary);
}

.version-item.selected {
  border-color: var(--color-primary);
  border-left-color: var(--color-primary);
}

.version-item.current {
  border-left-color: #4caf50;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.version-number {
  font-weight: 700;
  font-family: monospace;
  color: var(--color-primary);
}

.current-badge {
  background: #4caf50;
  color: white;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 700;
}

.version-message {
  font-size: 0.875rem;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.version-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.version-tags {
  display: flex;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}

.version-actions-inline {
  margin-top: var(--spacing-xs);
}

.btn-link {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
}

.btn-link:hover {
  text-decoration: underline;
}

/* Details Panel */
.details-panel {
  max-height: 100%;
  overflow-y: auto;
}

.detail-section {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--bg-input);
}

.detail-section h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.detail-row {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.detail-row .label {
  color: var(--text-secondary);
  min-width: 100px;
}

.detail-row .value {
  color: var(--text-primary);
}

/* Diff View */
.diff-summary {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-input);
}

.diff-stat {
  font-weight: 600;
  font-family: monospace;
}

.diff-stat.added {
  color: #4caf50;
}

.diff-stat.removed {
  color: #f44336;
}

.diff-stat.modified {
  color: #ff9800;
}

.diff-list {
  padding: var(--spacing-md);
}

.diff-item {
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  border-left: 3px solid;
}

.diff-item.added {
  border-left-color: #4caf50;
}

.diff-item.removed {
  border-left-color: #f44336;
}

.diff-item.modified {
  border-left-color: #ff9800;
}

.diff-path {
  font-family: monospace;
  font-weight: 600;
  margin-bottom: var(--spacing-xs);
}

.diff-values {
  font-family: monospace;
  font-size: 0.75rem;
}

.old-value {
  color: #f44336;
}

.new-value {
  color: #4caf50;
}

/* Config Preview */
.config-preview {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.config-item {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.config-label {
  color: var(--text-secondary);
}

.config-count {
  color: var(--text-primary);
  font-weight: 500;
}

/* RAG Sources */
.rag-sources {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.rag-source {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.source-title {
  color: var(--text-primary);
}

.source-score {
  color: var(--color-primary);
  font-weight: 600;
}

/* Tags List */
.tags-list {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-card);
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  min-width: 400px;
  max-width: 500px;
}

.modal h3 {
  margin: 0 0 var(--spacing-md) 0;
}

.modal-description {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: var(--spacing-md);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--bg-input);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-lg);
}

/* Utility */
.loading,
.error,
.empty {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--text-secondary);
}

.error {
  color: #f44336;
}

.version-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.75rem;
}

.btn-danger {
  background: #f44336;
  color: white;
}

.btn-danger:hover {
  background: #d32f2f;
}

.btn-outline {
  background: transparent;
  border: 1px solid var(--color-primary);
  color: var(--color-primary);
}

.btn-outline:hover {
  background: var(--color-primary);
  color: white;
}

/* Modal Large */
.modal-lg {
  max-width: 600px;
}

/* Import Section */
.import-section {
  margin-top: var(--spacing-md);
}

/* File Import UI */
.file-loaded {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.file-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-primary);
}

.file-icon {
  font-size: 1.25rem;
}

.file-name {
  flex: 1;
  font-size: 0.875rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-icon {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-xs);
  font-size: 0.875rem;
  border-radius: var(--radius-sm);
}

.btn-icon:hover {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.import-preview {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.preview-row {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.preview-row:last-child {
  margin-bottom: 0;
}

.preview-label {
  color: var(--text-secondary);
  min-width: 100px;
  font-size: 0.875rem;
}

.preview-value {
  color: var(--text-primary);
  font-size: 0.875rem;
}

.file-upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-lg);
  background: var(--bg-input);
  border: 2px dashed var(--text-tertiary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.file-upload-area:hover {
  border-color: var(--color-primary);
  background: rgba(0, 217, 255, 0.05);
}

.upload-icon {
  font-size: 2rem;
  color: var(--text-secondary);
}

.upload-hint {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

/* Simulation Results */
.simulation-results {
  background: rgba(0, 217, 255, 0.05);
}

.sim-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.sim-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.sim-stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.sim-stat-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.sim-stat.detected .sim-stat-value {
  color: #4caf50;
}

.sim-stat.blocked .sim-stat-value {
  color: #2196f3;
}

.sim-stat.compromised .sim-stat-value {
  color: #f44336;
}

.sim-meta {
  margin-bottom: var(--spacing-sm);
}

.mode-badge {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
}

.mode-badge.benign {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.mode-badge.threat {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

/* Simulation Import Preview */
.simulation-preview {
  border: 1px solid rgba(0, 217, 255, 0.3);
  background: rgba(0, 217, 255, 0.05);
}

.preview-header {
  margin-bottom: var(--spacing-sm);
}

.sim-badge {
  display: inline-block;
  padding: 4px 10px;
  background: rgba(0, 217, 255, 0.2);
  color: var(--color-primary);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
}

.mono {
  font-family: monospace;
  font-size: 0.8rem;
}

.sim-stats-preview {
  display: flex;
  gap: var(--spacing-md);
  margin: var(--spacing-md) 0;
  padding: var(--spacing-sm);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.mini-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.mini-stat-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-transform: uppercase;
}
</style>