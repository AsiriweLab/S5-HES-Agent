<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useHealthStore } from '@/stores/health'
import { useSettingsStore } from '@/stores/settings'
import { useModeStore } from '@/stores/mode'
import { useRouter } from 'vue-router'

const healthStore = useHealthStore()
const settingsStore = useSettingsStore()
const modeStore = useModeStore()
const router = useRouter()

// Scenario execution state
const executingScenario = ref<string | null>(null)
const scenarioError = ref<string | null>(null)

// Computed values for Research Integrity display
const verificationStatus = computed(() =>
  settingsStore.researchIntegrity.verificationEnabled ? 'Active' : 'Disabled'
)
const verificationClass = computed(() =>
  settingsStore.researchIntegrity.verificationEnabled ? 'success' : 'warning'
)

const strictModeStatus = computed(() =>
  settingsStore.researchIntegrity.strictMode ? 'On' : 'Off'
)
const strictModeClass = computed(() =>
  settingsStore.researchIntegrity.strictMode ? 'warning' : 'info'
)

const sourceAttributionStatus = computed(() =>
  settingsStore.researchIntegrity.sourceAttributionRequired ? 'Required' : 'Optional'
)
const sourceAttributionClass = computed(() =>
  settingsStore.researchIntegrity.sourceAttributionRequired ? 'success' : 'info'
)

// Mode switching
function setLLMMode() {
  modeStore.setMode('llm')
}

function setNoLLMMode() {
  modeStore.setMode('no-llm')
}

// Execute a pre-loaded scenario
async function executeScenario(scenarioId: string) {
  executingScenario.value = scenarioId
  scenarioError.value = null

  try {
    const result = await modeStore.executeScenario(scenarioId)
    // Navigate to simulation page after scenario is set up
    router.push('/simulation')
  } catch (e) {
    scenarioError.value = e instanceof Error ? e.message : 'Failed to execute scenario'
  } finally {
    executingScenario.value = null
  }
}

// Get difficulty badge class
function getDifficultyClass(difficulty: string): string {
  switch (difficulty) {
    case 'beginner': return 'success'
    case 'intermediate': return 'warning'
    case 'advanced': return 'error'
    case 'expert': return 'error'
    default: return 'info'
  }
}

onMounted(() => {
  healthStore.fetchHealth()
  settingsStore.initialize()
  modeStore.initialize()
})
</script>

<template>
  <div class="dashboard">
    <h2>Dashboard</h2>

    <div class="dashboard-grid">
      <!-- System Status Card -->
      <div class="card">
        <h3>System Status</h3>
        <div class="status-grid">
          <div class="status-item">
            <span class="label">API Status</span>
            <span :class="['status-badge', healthStore.isHealthy ? 'success' : 'error']">
              {{ healthStore.isHealthy ? 'Healthy' : 'Unavailable' }}
            </span>
          </div>
          <div class="status-item">
            <span class="label">Version</span>
            <span class="value">{{ healthStore.health?.version || 'N/A' }}</span>
          </div>
          <div class="status-item">
            <span class="label">Environment</span>
            <span class="value">{{ healthStore.health?.environment || 'N/A' }}</span>
          </div>
        </div>
      </div>

      <!-- Mode Selection Card -->
      <div class="card">
        <h3>Interaction Mode</h3>
        <div class="mode-selector">
          <button
            :class="['mode-btn', { active: modeStore.isLLMMode }]"
            @click="setLLMMode"
          >
            <span class="mode-icon">🤖</span>
            <span class="mode-label">LLM-Assisted</span>
            <span class="mode-desc">Natural language configuration</span>
          </button>
          <button
            :class="['mode-btn', { active: modeStore.isNoLLMMode }]"
            @click="setNoLLMMode"
          >
            <span class="mode-icon">📋</span>
            <span class="mode-label">No-LLM Mode</span>
            <span class="mode-desc">Manual configuration</span>
          </button>
        </div>
      </div>

      <!-- Quick Actions Card -->
      <div class="card">
        <h3>Quick Actions</h3>
        <div class="actions">
          <router-link to="/simulation" class="btn btn-primary">New Simulation</router-link>
          <router-link to="/home-builder" class="btn btn-secondary">Load Template</router-link>
          <router-link to="/history" class="btn btn-secondary">View Results</router-link>
        </div>
      </div>

      <!-- Research Integrity Status (Connected to Settings Store) -->
      <div class="card">
        <h3>Research Integrity</h3>
        <div class="status-grid">
          <div class="status-item">
            <span class="label">Verification Pipeline</span>
            <span :class="['status-badge', verificationClass]">{{ verificationStatus }}</span>
          </div>
          <div class="status-item">
            <span class="label">Strict Mode</span>
            <span :class="['status-badge', strictModeClass]">{{ strictModeStatus }}</span>
          </div>
          <div class="status-item">
            <span class="label">Source Attribution</span>
            <span :class="['status-badge', sourceAttributionClass]">{{ sourceAttributionStatus }}</span>
          </div>
        </div>
        <div class="card-footer">
          <router-link to="/settings" class="settings-link">Configure in Settings →</router-link>
        </div>
      </div>

      <!-- Pre-loaded Scenarios (Shown in No-LLM Mode) -->
      <div v-if="modeStore.isNoLLMMode" class="card scenarios-card">
        <h3>Pre-loaded Scenarios</h3>
        <p class="scenarios-description">
          Start with a reproducible research scenario. No LLM required.
        </p>

        <!-- Error Message -->
        <div v-if="scenarioError" class="error-banner">
          {{ scenarioError }}
        </div>

        <!-- Scenarios List -->
        <div class="scenarios-list">
          <div
            v-for="scenario in modeStore.scenarios"
            :key="scenario.id"
            class="scenario-item"
          >
            <div class="scenario-header">
              <span class="scenario-name">{{ scenario.name }}</span>
              <span :class="['difficulty-badge', getDifficultyClass(scenario.difficulty)]">
                {{ scenario.difficulty }}
              </span>
            </div>
            <p class="scenario-desc">{{ scenario.description }}</p>
            <div class="scenario-tags">
              <span v-for="tag in scenario.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
            <button
              class="btn btn-sm btn-primary"
              @click="executeScenario(scenario.id)"
              :disabled="executingScenario !== null"
            >
              <span v-if="executingScenario === scenario.id" class="spinner"></span>
              <span v-else>Launch</span>
            </button>
          </div>
        </div>

        <div v-if="modeStore.scenarios.length === 0" class="empty-state">
          <p>Loading scenarios...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard h2 {
  margin-bottom: var(--spacing-lg);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-lg);
}

.card h3 {
  margin-bottom: var(--spacing-md);
  font-size: 1.125rem;
  color: var(--text-primary);
}

.status-grid {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-item .label {
  color: var(--text-secondary);
}

.status-item .value {
  color: var(--text-primary);
  font-weight: 500;
}

.mode-selector {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all 0.2s;
  cursor: pointer;
}

.mode-btn:hover {
  border-color: var(--color-primary);
}

.mode-btn.active {
  border-color: var(--color-primary);
  background: rgba(0, 217, 255, 0.1);
}

.mode-icon {
  font-size: 1.5rem;
  margin-bottom: var(--spacing-xs);
}

.mode-label {
  font-weight: 600;
  color: var(--text-primary);
}

.mode-desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.actions .btn {
  text-align: center;
  text-decoration: none;
}

.card-footer {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--bg-input);
}

.settings-link {
  color: var(--color-primary);
  font-size: 0.875rem;
  text-decoration: none;
}

.settings-link:hover {
  text-decoration: underline;
}

/* Scenarios Card */
.scenarios-card {
  grid-column: span 2;
}

.scenarios-description {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: var(--spacing-md);
}

.error-banner {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-md);
  font-size: 0.875rem;
}

.scenarios-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
}

.scenario-item {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.scenario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.scenario-name {
  font-weight: 600;
  color: var(--text-primary);
}

.difficulty-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.difficulty-badge.success {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
}

.difficulty-badge.warning {
  background: rgba(217, 119, 6, 0.1);
  color: #d97706;
}

.difficulty-badge.error {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.scenario-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
  flex: 1;
}

.scenario-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  font-size: 0.7rem;
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

.scenario-item .btn {
  align-self: flex-start;
  margin-top: auto;
}

.empty-state {
  text-align: center;
  padding: var(--spacing-lg);
  color: var(--text-muted);
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .scenarios-card {
    grid-column: span 1;
  }
}
</style>