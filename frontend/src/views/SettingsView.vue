<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import HumanReviewQueue from '@/components/HumanReviewQueue.vue'
import { llmApi, type ProviderInfo } from '@/services/llmApi'

const settingsStore = useSettingsStore()

// LLM Provider state
const providers = ref<ProviderInfo[]>([])
const isLoadingProviders = ref(false)
const providerError = ref('')
const isSwitchingProvider = ref(false)
const switchMessage = ref('')

// Local state for form binding (to allow cancel without saving)
const localSettings = ref({
  verificationEnabled: true,
  strictMode: false,
  sourceAttributionRequired: true,
  confidenceThresholdPass: 0.85,
  confidenceThresholdFlag: 0.70,
  // LLM settings
  llmProvider: 'ollama',
  ollamaHost: 'http://localhost:11434',
  ollamaModel: 'llama3.1:8b-instruct-q4_K_M',
  openaiModel: 'gpt-4o',
  geminiModel: 'gemini-2.0-flash',
})

// Computed: Get current provider info
const currentProviderInfo = computed(() => {
  return providers.value.find(p => p.name === localSettings.value.llmProvider)
})

// Computed: Available models for current provider
const availableModels = computed(() => {
  const provider = currentProviderInfo.value
  if (!provider) return []
  return provider.available_models
})

// Computed: Current model for selected provider
const currentModel = computed({
  get() {
    if (localSettings.value.llmProvider === 'openai') {
      return localSettings.value.openaiModel
    } else if (localSettings.value.llmProvider === 'gemini') {
      return localSettings.value.geminiModel
    }
    return localSettings.value.ollamaModel
  },
  set(value: string) {
    if (localSettings.value.llmProvider === 'openai') {
      localSettings.value.openaiModel = value
    } else if (localSettings.value.llmProvider === 'gemini') {
      localSettings.value.geminiModel = value
    } else {
      localSettings.value.ollamaModel = value
    }
    checkChanges()
  }
})

const hasUnsavedChanges = ref(false)
const saveMessage = ref('')

// Fetch LLM providers from backend
async function fetchProviders() {
  isLoadingProviders.value = true
  providerError.value = ''
  try {
    const response = await llmApi.getProviders()
    providers.value = response.providers
    // Update local settings with active provider from backend
    if (response.active_provider) {
      localSettings.value.llmProvider = response.active_provider
    }
  } catch (error) {
    providerError.value = error instanceof Error ? error.message : 'Failed to fetch providers'
  } finally {
    isLoadingProviders.value = false
  }
}

// Handle provider selection change
async function onProviderChange(providerName: string) {
  const provider = providers.value.find(p => p.name === providerName)
  if (!provider) return

  // Check if provider is configured
  if (!provider.is_configured) {
    providerError.value = `${provider.display_name} requires ${provider.api_key_env_var} environment variable to be set in the backend.`
    // Revert to previous provider
    localSettings.value.llmProvider = settingsStore.llm.provider
    return
  }

  providerError.value = ''
  localSettings.value.llmProvider = providerName
  checkChanges()
}

// Sync local state from store
function syncFromStore() {
  localSettings.value = {
    verificationEnabled: settingsStore.researchIntegrity.verificationEnabled,
    strictMode: settingsStore.researchIntegrity.strictMode,
    sourceAttributionRequired: settingsStore.researchIntegrity.sourceAttributionRequired,
    confidenceThresholdPass: settingsStore.researchIntegrity.confidenceThresholdPass,
    confidenceThresholdFlag: settingsStore.researchIntegrity.confidenceThresholdFlag,
    llmProvider: settingsStore.llm.provider,
    ollamaHost: settingsStore.llm.ollamaHost,
    ollamaModel: settingsStore.llm.ollamaModel,
    openaiModel: settingsStore.llm.openaiModel,
    geminiModel: settingsStore.llm.geminiModel,
  }
  hasUnsavedChanges.value = false
}

// Check for changes
function checkChanges() {
  const store = settingsStore
  hasUnsavedChanges.value =
    localSettings.value.verificationEnabled !== store.researchIntegrity.verificationEnabled ||
    localSettings.value.strictMode !== store.researchIntegrity.strictMode ||
    localSettings.value.sourceAttributionRequired !== store.researchIntegrity.sourceAttributionRequired ||
    localSettings.value.confidenceThresholdPass !== store.researchIntegrity.confidenceThresholdPass ||
    localSettings.value.confidenceThresholdFlag !== store.researchIntegrity.confidenceThresholdFlag ||
    localSettings.value.llmProvider !== store.llm.provider ||
    localSettings.value.ollamaHost !== store.llm.ollamaHost ||
    localSettings.value.ollamaModel !== store.llm.ollamaModel ||
    localSettings.value.openaiModel !== store.llm.openaiModel ||
    localSettings.value.geminiModel !== store.llm.geminiModel
}

// Save settings to store (and localStorage via store)
async function saveSettings() {
  isSwitchingProvider.value = true
  switchMessage.value = ''

  try {
    // Update research integrity settings
    settingsStore.updateResearchIntegrity({
      verificationEnabled: localSettings.value.verificationEnabled,
      strictMode: localSettings.value.strictMode,
      sourceAttributionRequired: localSettings.value.sourceAttributionRequired,
      confidenceThresholdPass: localSettings.value.confidenceThresholdPass,
      confidenceThresholdFlag: localSettings.value.confidenceThresholdFlag,
    })

    // Update LLM settings in store
    settingsStore.updateLLM({
      provider: localSettings.value.llmProvider,
      ollamaHost: localSettings.value.ollamaHost,
      ollamaModel: localSettings.value.ollamaModel,
      openaiModel: localSettings.value.openaiModel,
      geminiModel: localSettings.value.geminiModel,
    })

    // Switch provider on backend (persistent change)
    let model: string
    if (localSettings.value.llmProvider === 'openai') {
      model = localSettings.value.openaiModel
    } else if (localSettings.value.llmProvider === 'gemini') {
      model = localSettings.value.geminiModel
    } else {
      model = localSettings.value.ollamaModel
    }

    try {
      const result = await llmApi.switchProvider(localSettings.value.llmProvider, model)
      switchMessage.value = result.message
    } catch (error) {
      // Provider switch failed on backend - this is a warning, not a failure
      // Settings are still saved locally
      const errorMsg = error instanceof Error ? error.message : 'Provider switch failed'
      switchMessage.value = `Settings saved locally. Backend switch: ${errorMsg}`
    }

    hasUnsavedChanges.value = false
    saveMessage.value = 'Settings saved successfully!'
    setTimeout(() => {
      saveMessage.value = ''
      switchMessage.value = ''
    }, 5000)
  } finally {
    isSwitchingProvider.value = false
  }
}

// Reset to defaults
function resetToDefaults() {
  settingsStore.resetToDefaults()
  syncFromStore()
  saveMessage.value = 'Settings reset to defaults'
  setTimeout(() => {
    saveMessage.value = ''
  }, 3000)
}

// Initialize
onMounted(async () => {
  settingsStore.initialize()
  syncFromStore()
  await fetchProviders()
})
</script>

<template>
  <div class="settings-view">
    <h2>Settings</h2>

    <div class="settings-grid">
      <!-- Anti-Hallucination Settings -->
      <div class="card">
        <h3>🛡️ Research Integrity</h3>
        <p class="section-desc">Critical settings for preventing AI hallucinations</p>

        <div class="setting-item">
          <div class="setting-info">
            <label>Verification Pipeline</label>
            <span class="desc">Validate all LLM outputs before use</span>
          </div>
          <input
            type="checkbox"
            v-model="localSettings.verificationEnabled"
            @change="checkChanges"
          />
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <label>Strict Mode</label>
            <span class="desc">Require human approval for ALL AI outputs</span>
          </div>
          <input
            type="checkbox"
            v-model="localSettings.strictMode"
            @change="checkChanges"
          />
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <label>Source Attribution Required</label>
            <span class="desc">Every fact must cite its source</span>
          </div>
          <input
            type="checkbox"
            v-model="localSettings.sourceAttributionRequired"
            @change="checkChanges"
          />
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <label>Auto-Pass Threshold</label>
            <span class="desc">Confidence ≥ {{ localSettings.confidenceThresholdPass.toFixed(2) }} auto-approved</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="1"
            step="0.05"
            v-model.number="localSettings.confidenceThresholdPass"
            @input="checkChanges"
          />
        </div>

        <div class="setting-item">
          <div class="setting-info">
            <label>Review Threshold</label>
            <span class="desc">Confidence ≥ {{ localSettings.confidenceThresholdFlag.toFixed(2) }} flagged for review</span>
          </div>
          <input
            type="range"
            min="0.3"
            max="0.9"
            step="0.05"
            v-model.number="localSettings.confidenceThresholdFlag"
            @input="checkChanges"
          />
        </div>
      </div>

      <!-- LLM Settings -->
      <div class="card">
        <h3>🤖 LLM Configuration</h3>
        <p class="section-desc">Select your LLM provider and model</p>

        <!-- Configuration Info -->
        <div class="info-box">
          <strong>LLM Provider Selection:</strong> Changes are automatically saved to the backend <code>.env</code> file.
          <ul>
            <li><strong>Ollama:</strong> Free, local inference (requires Ollama running)</li>
            <li><strong>OpenAI:</strong> Cloud API (set <code>OPENAI_API_KEY</code> in <code>.env</code>)</li>
            <li><strong>Gemini:</strong> Cloud API (set <code>GEMINI_API_KEY</code> in <code>.env</code>)</li>
          </ul>
        </div>

        <!-- Provider Error -->
        <div v-if="providerError" class="error-box">
          {{ providerError }}
        </div>

        <!-- Loading State -->
        <div v-if="isLoadingProviders" class="loading-state">
          Loading providers...
        </div>

        <!-- Provider Selection -->
        <div class="setting-section" v-if="!isLoadingProviders">
          <label class="section-label">LLM Provider</label>
          <div class="provider-options">
            <label
              v-for="provider in providers"
              :key="provider.name"
              class="provider-option"
              :class="{
                'selected': localSettings.llmProvider === provider.name,
                'disabled': !provider.is_configured
              }"
            >
              <input
                type="radio"
                name="llmProvider"
                :value="provider.name"
                :checked="localSettings.llmProvider === provider.name"
                :disabled="!provider.is_configured"
                @change="onProviderChange(provider.name)"
              />
              <div class="provider-content">
                <span class="provider-name">{{ provider.display_name }}</span>
                <span class="provider-status" :class="provider.is_configured ? 'configured' : 'not-configured'">
                  {{ provider.status_message }}
                </span>
              </div>
            </label>
          </div>
        </div>

        <!-- Model Selection -->
        <div class="setting-item" v-if="currentProviderInfo && currentProviderInfo.is_configured">
          <div class="setting-info">
            <label>Model</label>
            <span class="desc">Select model for {{ currentProviderInfo.display_name }}</span>
          </div>
          <select
            v-model="currentModel"
            class="select-input"
            @change="checkChanges"
          >
            <option
              v-for="model in availableModels"
              :key="model"
              :value="model"
            >
              {{ model }}
            </option>
          </select>
        </div>

        <!-- Ollama Host (only for Ollama) -->
        <div class="setting-item" v-if="localSettings.llmProvider === 'ollama'">
          <div class="setting-info">
            <label>Ollama Host</label>
            <span class="desc">Local Ollama server address</span>
          </div>
          <input
            type="text"
            v-model="localSettings.ollamaHost"
            class="text-input"
            @input="checkChanges"
          />
        </div>

        <!-- Switch Message -->
        <div v-if="switchMessage" class="switch-message">
          {{ switchMessage }}
        </div>
      </div>
    </div>

    <!-- Human Review Queue Section -->
    <div class="review-section">
      <HumanReviewQueue />
    </div>

    <div class="actions">
      <button
        class="btn btn-primary"
        @click="saveSettings"
        :disabled="!hasUnsavedChanges || isSwitchingProvider"
      >
        {{ isSwitchingProvider ? 'Saving...' : 'Save Settings' }}
      </button>
      <button class="btn btn-secondary" @click="resetToDefaults" :disabled="isSwitchingProvider">
        Reset to Defaults
      </button>
      <span v-if="saveMessage" class="save-message">{{ saveMessage }}</span>
      <span v-if="hasUnsavedChanges" class="unsaved-indicator">Unsaved changes</span>
    </div>
  </div>
</template>

<style scoped>
.settings-view h2 {
  margin-bottom: var(--spacing-lg);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: var(--spacing-lg);
}

.card h3 {
  margin-bottom: var(--spacing-xs);
}

.section-desc {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: var(--spacing-lg);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--bg-input);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.setting-info label {
  font-weight: 500;
  color: var(--text-primary);
}

.setting-info .desc {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

input[type="checkbox"] {
  width: 20px;
  height: 20px;
  accent-color: var(--color-primary);
}

input[type="range"] {
  width: 120px;
  accent-color: var(--color-primary);
}

.text-input {
  width: 200px;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--text-muted);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.text-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.actions {
  margin-top: var(--spacing-xl);
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-message {
  color: var(--status-success);
  font-size: 0.875rem;
}

.unsaved-indicator {
  color: var(--status-warning);
  font-size: 0.875rem;
  font-style: italic;
}

.review-section {
  margin-top: var(--spacing-xl);
}

/* Info and Error Boxes */
.info-box {
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.info-box strong {
  color: var(--color-primary);
}

.info-box ul {
  margin: var(--spacing-sm) 0 0 var(--spacing-lg);
  padding: 0;
}

.info-box li {
  margin-bottom: var(--spacing-xs);
}

.info-box code {
  background: rgba(0, 0, 0, 0.2);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: monospace;
  font-size: 0.8rem;
}

.error-box {
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid rgba(220, 53, 69, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-md);
  color: #dc3545;
  font-size: 0.875rem;
}

.loading-state {
  color: var(--text-secondary);
  font-style: italic;
  padding: var(--spacing-md);
}

/* Provider Selection */
.setting-section {
  margin-bottom: var(--spacing-lg);
}

.section-label {
  display: block;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.provider-options {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.provider-option {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
  flex: 1;
  min-width: 140px;
  max-width: 200px;
}

.provider-option:hover:not(.disabled) {
  border-color: var(--color-primary);
}

.provider-option.selected {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.provider-option.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.provider-option input[type="radio"] {
  margin-top: 3px;
  accent-color: var(--color-primary);
}

.provider-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.provider-name {
  font-weight: 500;
  color: var(--text-primary);
}

.provider-status {
  font-size: 0.75rem;
}

.provider-status.configured {
  color: var(--status-success);
}

.provider-status.not-configured {
  color: var(--status-warning);
}

/* Select Input */
.select-input {
  width: 250px;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--text-muted);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.875rem;
  cursor: pointer;
}

.select-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.switch-message {
  margin-top: var(--spacing-md);
  padding: var(--spacing-sm);
  background: rgba(99, 102, 241, 0.1);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  color: var(--text-secondary);
}
</style>