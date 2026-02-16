<script setup lang="ts">
import { ref, computed, watch } from 'vue'

// Types
type ProtocolType = 'mqtt' | 'coap' | 'http' | 'websocket'
type CloudPlatform = 'aws' | 'azure' | 'gcp' | 'none'

interface ProtocolConfig {
  type: ProtocolType
  host: string
  port: number
  useTls: boolean
  username?: string
  password?: string
  clientId: string
  // MQTT specific
  qos?: 0 | 1 | 2
  cleanSession?: boolean
  keepAlive?: number
  lwtTopic?: string
  lwtPayload?: string
  // HTTP specific
  baseUrl?: string
  authType?: 'none' | 'basic' | 'bearer' | 'api_key'
  apiKey?: string
  bearerToken?: string
  // WebSocket specific
  path?: string
  pingInterval?: number
  // Cloud platform
  cloudPlatform?: CloudPlatform
  cloudConfig?: Record<string, string>
}

// Props & Emits
const props = defineProps<{
  modelValue?: Partial<ProtocolConfig>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ProtocolConfig): void
  (e: 'save', config: ProtocolConfig): void
  (e: 'cancel'): void
}>()

// State
const currentStep = ref(1)
const totalSteps = 4

const config = ref<ProtocolConfig>({
  type: 'mqtt',
  host: 'localhost',
  port: 1883,
  useTls: false,
  clientId: `smart-hes-${Date.now().toString(36)}`,
  qos: 1,
  cleanSession: true,
  keepAlive: 60,
  authType: 'none',
  path: '/ws',
  pingInterval: 30,
  cloudPlatform: 'none',
  cloudConfig: {},
})

// Initialize from props
watch(() => props.modelValue, (val) => {
  if (val) {
    config.value = { ...config.value, ...val }
  }
}, { immediate: true })

// Protocol options
const protocols = [
  { id: 'mqtt', name: 'MQTT', icon: '📡', description: 'Message Queuing Telemetry Transport', defaultPort: 1883 },
  { id: 'coap', name: 'CoAP', icon: '📦', description: 'Constrained Application Protocol', defaultPort: 5683 },
  { id: 'http', name: 'HTTP/REST', icon: '🌐', description: 'REST API Communication', defaultPort: 80 },
  { id: 'websocket', name: 'WebSocket', icon: '🔌', description: 'Full-duplex Communication', defaultPort: 8080 },
]

const cloudPlatforms = [
  { id: 'none', name: 'No Cloud', icon: '🏠', description: 'Local/Custom broker' },
  { id: 'aws', name: 'AWS IoT Core', icon: '☁️', description: 'Amazon Web Services' },
  { id: 'azure', name: 'Azure IoT Hub', icon: '🔷', description: 'Microsoft Azure' },
  { id: 'gcp', name: 'Google Cloud IoT', icon: '🔶', description: 'Google Cloud Platform' },
]

const qosOptions: Array<{ value: 0 | 1 | 2; label: string; description: string }> = [
  { value: 0, label: 'QoS 0 - At Most Once', description: 'Fire and forget' },
  { value: 1, label: 'QoS 1 - At Least Once', description: 'Acknowledged delivery' },
  { value: 2, label: 'QoS 2 - Exactly Once', description: 'Assured delivery' },
]

// Computed
const selectedProtocol = computed(() => protocols.find(p => p.id === config.value.type))
const selectedCloud = computed(() => cloudPlatforms.find(c => c.id === config.value.cloudPlatform))

const stepTitle = computed(() => {
  switch (currentStep.value) {
    case 1: return 'Select Protocol'
    case 2: return 'Connection Settings'
    case 3: return 'Protocol Options'
    case 4: return 'Review & Save'
    default: return ''
  }
})

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return !!config.value.type
    case 2: return !!config.value.host && config.value.port > 0
    case 3: return true
    case 4: return true
    default: return false
  }
})

// Methods
function selectProtocol(type: ProtocolType) {
  config.value.type = type
  const proto = protocols.find(p => p.id === type)
  if (proto) {
    config.value.port = proto.defaultPort
  }
}

function selectCloudPlatform(platform: CloudPlatform) {
  config.value.cloudPlatform = platform

  // Set default values based on platform
  if (platform === 'aws') {
    config.value.port = 8883
    config.value.useTls = true
  } else if (platform === 'azure') {
    config.value.port = 8883
    config.value.useTls = true
  } else if (platform === 'gcp') {
    config.value.port = 8883
    config.value.useTls = true
  }
}

function nextStep() {
  if (currentStep.value < totalSteps && canProceed.value) {
    currentStep.value++
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

function generateClientId() {
  config.value.clientId = `smart-hes-${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 4)}`
}

function saveConfig() {
  emit('update:modelValue', config.value)
  emit('save', config.value)
}

function cancel() {
  emit('cancel')
}

function getConfigSummary() {
  const summary: { label: string; value: string }[] = [
    { label: 'Protocol', value: selectedProtocol.value?.name || config.value.type },
    { label: 'Host', value: config.value.host },
    { label: 'Port', value: config.value.port.toString() },
    { label: 'TLS', value: config.value.useTls ? 'Enabled' : 'Disabled' },
    { label: 'Client ID', value: config.value.clientId },
  ]

  if (config.value.cloudPlatform !== 'none') {
    summary.push({ label: 'Cloud Platform', value: selectedCloud.value?.name || '' })
  }

  if (config.value.type === 'mqtt') {
    summary.push({ label: 'QoS Level', value: `QoS ${config.value.qos}` })
    summary.push({ label: 'Clean Session', value: config.value.cleanSession ? 'Yes' : 'No' })
  }

  if (config.value.type === 'http') {
    summary.push({ label: 'Auth Type', value: config.value.authType || 'None' })
  }

  return summary
}
</script>

<template>
  <div class="protocol-wizard">
    <!-- Header -->
    <div class="wizard-header">
      <h2>IoT Protocol Configuration</h2>
      <p>Configure communication protocols for your IoT devices</p>
    </div>

    <!-- Progress Steps -->
    <div class="wizard-steps">
      <div
        v-for="step in totalSteps"
        :key="step"
        class="step"
        :class="{
          active: currentStep === step,
          completed: currentStep > step,
        }"
      >
        <div class="step-number">{{ step }}</div>
        <span class="step-label">
          {{ step === 1 ? 'Protocol' : step === 2 ? 'Connection' : step === 3 ? 'Options' : 'Review' }}
        </span>
      </div>
    </div>

    <!-- Step Content -->
    <div class="wizard-content">
      <h3>{{ stepTitle }}</h3>

      <!-- Step 1: Protocol Selection -->
      <div v-if="currentStep === 1" class="step-content">
        <div class="protocol-grid">
          <div
            v-for="proto in protocols"
            :key="proto.id"
            class="protocol-card"
            :class="{ selected: config.type === proto.id }"
            @click="selectProtocol(proto.id as ProtocolType)"
          >
            <span class="protocol-icon">{{ proto.icon }}</span>
            <div class="protocol-info">
              <h4>{{ proto.name }}</h4>
              <p>{{ proto.description }}</p>
            </div>
            <div class="protocol-check" v-if="config.type === proto.id">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
          </div>
        </div>

        <div class="cloud-section">
          <h4>Cloud Platform (Optional)</h4>
          <div class="cloud-grid">
            <div
              v-for="cloud in cloudPlatforms"
              :key="cloud.id"
              class="cloud-card"
              :class="{ selected: config.cloudPlatform === cloud.id }"
              @click="selectCloudPlatform(cloud.id as CloudPlatform)"
            >
              <span class="cloud-icon">{{ cloud.icon }}</span>
              <span class="cloud-name">{{ cloud.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 2: Connection Settings -->
      <div v-if="currentStep === 2" class="step-content">
        <div class="form-grid">
          <div class="form-group">
            <label>Host / Endpoint</label>
            <input
              v-model="config.host"
              type="text"
              placeholder="localhost or broker.example.com"
            />
          </div>

          <div class="form-group">
            <label>Port</label>
            <input
              v-model.number="config.port"
              type="number"
              min="1"
              max="65535"
            />
          </div>

          <div class="form-group full-width">
            <label>Client ID</label>
            <div class="input-with-button">
              <input v-model="config.clientId" type="text" />
              <button class="btn btn-ghost" @click="generateClientId">Generate</button>
            </div>
          </div>

          <div class="form-group checkbox-group">
            <label class="checkbox-label">
              <input v-model="config.useTls" type="checkbox" />
              <span>Enable TLS/SSL</span>
            </label>
          </div>

          <div class="form-group" v-if="config.type !== 'http'">
            <label>Username (Optional)</label>
            <input v-model="config.username" type="text" placeholder="Optional" />
          </div>

          <div class="form-group" v-if="config.type !== 'http'">
            <label>Password (Optional)</label>
            <input v-model="config.password" type="password" placeholder="Optional" />
          </div>
        </div>

        <!-- Cloud-specific settings -->
        <div v-if="config.cloudPlatform === 'aws'" class="cloud-config">
          <h4>AWS IoT Core Settings</h4>
          <div class="form-group full-width">
            <label>AWS Endpoint</label>
            <input
              v-model="config.host"
              type="text"
              placeholder="xxx.iot.region.amazonaws.com"
            />
          </div>
          <p class="hint">Use certificate-based authentication for production</p>
        </div>

        <div v-if="config.cloudPlatform === 'azure'" class="cloud-config">
          <h4>Azure IoT Hub Settings</h4>
          <div class="form-group full-width">
            <label>IoT Hub Hostname</label>
            <input
              v-model="config.host"
              type="text"
              placeholder="your-hub.azure-devices.net"
            />
          </div>
        </div>

        <div v-if="config.cloudPlatform === 'gcp'" class="cloud-config">
          <h4>Google Cloud IoT Settings</h4>
          <div class="form-group full-width">
            <label>Project ID</label>
            <input
              v-model="config.cloudConfig!.projectId"
              type="text"
              placeholder="your-project-id"
            />
          </div>
          <div class="form-group full-width">
            <label>Registry ID</label>
            <input
              v-model="config.cloudConfig!.registryId"
              type="text"
              placeholder="your-registry-id"
            />
          </div>
        </div>
      </div>

      <!-- Step 3: Protocol Options -->
      <div v-if="currentStep === 3" class="step-content">
        <!-- MQTT Options -->
        <div v-if="config.type === 'mqtt'" class="protocol-options">
          <h4>MQTT Settings</h4>

          <div class="form-group">
            <label>Quality of Service (QoS)</label>
            <div class="qos-options">
              <div
                v-for="qos in qosOptions"
                :key="qos.value"
                class="qos-option"
                :class="{ selected: config.qos === qos.value }"
                @click="config.qos = qos.value"
              >
                <div class="qos-header">
                  <span class="qos-value">{{ qos.value }}</span>
                  <span class="qos-label">{{ qos.label }}</span>
                </div>
                <p class="qos-desc">{{ qos.description }}</p>
              </div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input v-model="config.cleanSession" type="checkbox" />
                <span>Clean Session</span>
              </label>
            </div>

            <div class="form-group">
              <label>Keep Alive (seconds)</label>
              <input v-model.number="config.keepAlive" type="number" min="10" max="300" />
            </div>
          </div>

          <div class="form-group full-width">
            <label>Last Will Topic (Optional)</label>
            <input v-model="config.lwtTopic" type="text" placeholder="devices/{device_id}/status" />
          </div>

          <div class="form-group full-width">
            <label>Last Will Payload (Optional)</label>
            <input v-model="config.lwtPayload" type="text" placeholder="offline" />
          </div>
        </div>

        <!-- HTTP Options -->
        <div v-if="config.type === 'http'" class="protocol-options">
          <h4>HTTP/REST Settings</h4>

          <div class="form-group full-width">
            <label>Base URL</label>
            <input v-model="config.baseUrl" type="text" placeholder="https://api.example.com" />
          </div>

          <div class="form-group">
            <label>Authentication Type</label>
            <select v-model="config.authType">
              <option value="none">None</option>
              <option value="basic">Basic Auth</option>
              <option value="bearer">Bearer Token</option>
              <option value="api_key">API Key</option>
            </select>
          </div>

          <div v-if="config.authType === 'bearer'" class="form-group full-width">
            <label>Bearer Token</label>
            <input v-model="config.bearerToken" type="password" />
          </div>

          <div v-if="config.authType === 'api_key'" class="form-group full-width">
            <label>API Key</label>
            <input v-model="config.apiKey" type="password" />
          </div>
        </div>

        <!-- WebSocket Options -->
        <div v-if="config.type === 'websocket'" class="protocol-options">
          <h4>WebSocket Settings</h4>

          <div class="form-group">
            <label>Path</label>
            <input v-model="config.path" type="text" placeholder="/ws" />
          </div>

          <div class="form-group">
            <label>Ping Interval (seconds)</label>
            <input v-model.number="config.pingInterval" type="number" min="10" max="120" />
          </div>
        </div>

        <!-- CoAP Options -->
        <div v-if="config.type === 'coap'" class="protocol-options">
          <h4>CoAP Settings</h4>
          <p class="hint">CoAP uses confirmable (CON) messages by default for reliable delivery.</p>
        </div>
      </div>

      <!-- Step 4: Review -->
      <div v-if="currentStep === 4" class="step-content">
        <div class="review-section">
          <h4>Configuration Summary</h4>
          <div class="config-summary">
            <div
              v-for="item in getConfigSummary()"
              :key="item.label"
              class="summary-item"
            >
              <span class="summary-label">{{ item.label }}</span>
              <span class="summary-value">{{ item.value }}</span>
            </div>
          </div>
        </div>

        <div class="review-note">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
          <p>Review your configuration before saving. You can go back to make changes.</p>
        </div>
      </div>
    </div>

    <!-- Footer Actions -->
    <div class="wizard-footer">
      <button class="btn btn-ghost" @click="cancel">Cancel</button>
      <div class="footer-right">
        <button
          v-if="currentStep > 1"
          class="btn btn-ghost"
          @click="prevStep"
        >
          Back
        </button>
        <button
          v-if="currentStep < totalSteps"
          class="btn btn-primary"
          :disabled="!canProceed"
          @click="nextStep"
        >
          Next
        </button>
        <button
          v-if="currentStep === totalSteps"
          class="btn btn-primary"
          @click="saveConfig"
        >
          Save Configuration
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.protocol-wizard {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  max-width: 800px;
  margin: 0 auto;
}

.wizard-header {
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.wizard-header h2 {
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
}

.wizard-header p {
  margin: 0;
  color: var(--text-secondary);
}

/* Steps Progress */
.wizard-steps {
  display: flex;
  justify-content: center;
  gap: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.step.active .step-number {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.step.completed .step-number {
  background: var(--color-success);
  border-color: var(--color-success);
  color: white;
}

.step-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.step.active .step-label {
  color: var(--color-primary);
  font-weight: 600;
}

/* Content */
.wizard-content {
  min-height: 400px;
}

.wizard-content h3 {
  font-size: 1.1rem;
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--text-primary);
}

.step-content h4 {
  font-size: 0.95rem;
  margin: var(--spacing-lg) 0 var(--spacing-md) 0;
  color: var(--text-primary);
}

/* Protocol Grid */
.protocol-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.protocol-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.protocol-card:hover {
  border-color: var(--color-primary);
}

.protocol-card.selected {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.protocol-icon {
  font-size: 2rem;
}

.protocol-info h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1rem;
}

.protocol-info p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.protocol-check {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  color: var(--color-primary);
}

/* Cloud Grid */
.cloud-section {
  margin-top: var(--spacing-xl);
}

.cloud-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
}

.cloud-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.cloud-card:hover {
  border-color: var(--color-primary);
}

.cloud-card.selected {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.cloud-icon {
  font-size: 1.5rem;
}

.cloud-name {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-align: center;
}

/* Form Styles */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group.full-width {
  grid-column: 1 / -1;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-group input,
.form-group select {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.input-with-button {
  display: flex;
  gap: var(--spacing-sm);
}

.input-with-button input {
  flex: 1;
}

.checkbox-group {
  justify-content: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.checkbox-label input {
  width: 18px;
  height: 18px;
}

.form-row {
  display: flex;
  gap: var(--spacing-lg);
  align-items: flex-end;
}

/* QoS Options */
.qos-options {
  display: flex;
  gap: var(--spacing-md);
}

.qos-option {
  flex: 1;
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.qos-option:hover {
  border-color: var(--color-primary);
}

.qos-option.selected {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.qos-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.qos-value {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.8rem;
}

.qos-label {
  font-weight: 500;
  font-size: 0.85rem;
}

.qos-desc {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Cloud Config */
.cloud-config {
  margin-top: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: var(--spacing-sm);
}

/* Review */
.review-section {
  margin-bottom: var(--spacing-xl);
}

.config-summary {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.summary-item {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--border-color);
}

.summary-item:last-child {
  border-bottom: none;
}

.summary-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.summary-value {
  color: var(--text-primary);
  font-family: monospace;
}

.review-note {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  color: var(--color-info);
}

.review-note svg {
  flex-shrink: 0;
}

.review-note p {
  margin: 0;
  font-size: 0.85rem;
}

/* Footer */
.wizard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
}

.footer-right {
  display: flex;
  gap: var(--spacing-sm);
}

/* Responsive */
@media (max-width: 768px) {
  .protocol-grid {
    grid-template-columns: 1fr;
  }

  .cloud-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .qos-options {
    flex-direction: column;
  }

  .wizard-steps {
    gap: var(--spacing-md);
  }

  .step-label {
    display: none;
  }
}
</style>
