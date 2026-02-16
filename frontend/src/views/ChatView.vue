<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore, type CreatedHome, type CreatedThreat, type CreatedScenario } from '@/stores/chat'
import ChatHistory from '@/components/ChatHistory.vue'

const chatStore = useChatStore()
const router = useRouter()
const showHistory = ref(false)

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const useStreaming = ref(true)
const useActionMode = ref(true) // Enable action mode by default

// Notification for created resources
const showHomeCreatedNotification = ref(false)
const createdHomeInfo = ref<CreatedHome | null>(null)
const showThreatCreatedNotification = ref(false)
const createdThreatInfo = ref<CreatedThreat | null>(null)
const showScenarioCreatedNotification = ref(false)
const createdScenarioInfo = ref<{ scenario: CreatedScenario; home?: CreatedHome; threat?: CreatedThreat } | null>(null)

// Computed
const messages = computed(() => chatStore.messages)
const isLoading = computed(() => chatStore.isLoading)
const isStreaming = computed(() => chatStore.isStreaming)
const health = computed(() => chatStore.health)
const isHealthy = computed(() => chatStore.isHealthy)
const useRag = computed(() => chatStore.useRag)
const error = computed(() => chatStore.error)

// Auto-scroll to bottom when messages change
watch(messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return

  const message = inputMessage.value
  inputMessage.value = ''

  // Use action mode for commands that might create resources
  if (useActionMode.value) {
    const result = await chatStore.sendMessageWithAction(message)
    // Check for scenario first (composite home + threat)
    if (result?.scenario) {
      createdScenarioInfo.value = {
        scenario: result.scenario,
        home: result.home,
        threat: result.threat,
      }
      showScenarioCreatedNotification.value = true
    } else if (result?.home) {
      createdHomeInfo.value = result.home
      showHomeCreatedNotification.value = true
    } else if (result?.threat) {
      createdThreatInfo.value = result.threat
      showThreatCreatedNotification.value = true
    }
  } else if (useStreaming.value) {
    await chatStore.sendMessageStream(message)
  } else {
    await chatStore.sendMessage(message)
  }
}

function dismissHomeNotification() {
  showHomeCreatedNotification.value = false
  createdHomeInfo.value = null
  chatStore.clearCreatedResources()
}

function dismissThreatNotification() {
  showThreatCreatedNotification.value = false
  createdThreatInfo.value = null
  chatStore.clearCreatedResources()
}

function goToHomeBuilder() {
  // Store the created home data in sessionStorage for the Home Builder to load
  if (createdHomeInfo.value) {
    sessionStorage.setItem('chatCreatedHome', JSON.stringify(createdHomeInfo.value))
  }
  dismissHomeNotification()
  router.push('/home-builder')
}

function goToThreatBuilder() {
  // Store the created threat data in sessionStorage for the Threat Builder to load
  if (createdThreatInfo.value) {
    sessionStorage.setItem('chatCreatedThreat', JSON.stringify(createdThreatInfo.value))
  }
  dismissThreatNotification()
  router.push('/threat-builder')
}

function dismissScenarioNotification() {
  showScenarioCreatedNotification.value = false
  createdScenarioInfo.value = null
  chatStore.clearCreatedResources()
}

function goToSimulation() {
  // Store both home and threat data for the simulation view
  if (createdScenarioInfo.value?.home) {
    sessionStorage.setItem('chatCreatedHome', JSON.stringify(createdScenarioInfo.value.home))
  }
  if (createdScenarioInfo.value?.threat) {
    sessionStorage.setItem('chatCreatedThreat', JSON.stringify(createdScenarioInfo.value.threat))
  }
  if (createdScenarioInfo.value?.scenario) {
    sessionStorage.setItem('chatCreatedScenario', JSON.stringify(createdScenarioInfo.value.scenario))
  }
  dismissScenarioNotification()
  router.push('/simulation')
}

function clearChat() {
  chatStore.clearCurrentSession()
}

function newChat() {
  chatStore.createSession()
  // Add welcome message to new chat
  chatStore.addMessage({
    role: 'assistant',
    content: 'Hello! I\'m your S5-HES Agent assistant. I can help you configure smart home simulations, understand IoT security threats, and generate synthetic datasets for cybersecurity research. How can I help you today?'
  })
}

function toggleRag() {
  chatStore.toggleRag()
}

function usePrompt(prompt: string) {
  inputMessage.value = prompt
}

function stopGeneration() {
  chatStore.stopGeneration()
}

onMounted(() => {
  // Create initial session if none exists
  if (!chatStore.currentSession) {
    chatStore.createSession()
    // Add welcome message
    chatStore.addMessage({
      role: 'assistant',
      content: 'Hello! I\'m your S5-HES Agent assistant. I can help you configure smart home simulations, understand IoT security threats, and generate synthetic datasets for cybersecurity research. How can I help you today?'
    })
  }
  scrollToBottom()
})
</script>

<template>
  <div class="chat-view">
    <div class="chat-header">
      <div class="header-title">
        <h2>AI Assistant</h2>
        <span class="status-badge" :class="isHealthy ? 'success' : 'error'">
          <span class="status-dot" :class="isHealthy ? 'online' : 'offline'"></span>
          {{ isHealthy ? 'Online' : 'Offline' }}
        </span>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost btn-sm" @click="showHistory = !showHistory" title="Toggle History">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
          History
        </button>
        <button class="btn btn-ghost btn-sm" @click="newChat" title="New Chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New
        </button>
        <button class="btn btn-ghost btn-sm" @click="clearChat" title="Clear Chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          Clear
        </button>
      </div>
    </div>

    <!-- History Panel -->
    <div v-if="showHistory" class="history-panel card">
      <ChatHistory />
    </div>

    <div class="chat-container card" :class="{ 'with-history': showHistory }">
      <div class="messages" ref="messagesContainer">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <span v-if="msg.role === 'user'">U</span>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
            </svg>
          </div>
          <div class="message-body">
            <div class="message-content" :class="{ streaming: msg.isStreaming }">
              <div class="markdown-content" v-html="formatMessage(msg.content)"></div>
              <span v-if="msg.isStreaming" class="cursor"></span>
            </div>
            <div v-if="msg.sources && msg.sources.length > 0" class="message-sources">
              <span class="sources-label">Sources:</span>
              <span v-for="(source, idx) in msg.sources" :key="idx" class="source-tag">
                {{ source }}
              </span>
            </div>
            <div v-if="msg.confidence" class="message-meta">
              <span class="confidence" :class="msg.confidence">
                Confidence: {{ msg.confidence }}
              </span>
            </div>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="isLoading && !isStreaming" class="message assistant">
          <div class="message-avatar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
            </svg>
          </div>
          <div class="message-body">
            <div class="message-content loading">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="messages.length === 0" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <p>Start a conversation with the AI assistant</p>
        </div>
      </div>

      <!-- Error banner -->
      <div v-if="error" class="error-banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>{{ error }}</span>
        <button class="btn btn-ghost btn-sm" @click="chatStore.clearError()">Dismiss</button>
      </div>

      <div class="input-area">
        <div class="input-options">
          <label class="toggle-option" title="Enable Action Mode (execute commands like 'build a home')">
            <input type="checkbox" v-model="useActionMode" />
            <span class="toggle-label">Action</span>
          </label>
          <label class="toggle-option" title="Enable RAG (Knowledge Base)">
            <input type="checkbox" :checked="useRag" @change="toggleRag" />
            <span class="toggle-label">RAG</span>
          </label>
          <label class="toggle-option" title="Enable Streaming (disabled in action mode)" :class="{ disabled: useActionMode }">
            <input type="checkbox" v-model="useStreaming" :disabled="useActionMode" />
            <span class="toggle-label">Stream</span>
          </label>
        </div>
        <div class="input-row">
          <input
            v-model="inputMessage"
            type="text"
            placeholder="Ask about IoT security, smart home devices, or simulation..."
            @keyup.enter="sendMessage"
            :disabled="isLoading"
            class="input"
          />
          <!-- Stop button shown during generation -->
          <button
            v-if="isLoading"
            class="btn btn-stop"
            @click="stopGeneration"
            title="Stop generation"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2"></rect>
            </svg>
          </button>
          <!-- Send button shown when not loading -->
          <button
            v-else
            class="btn btn-primary"
            @click="sendMessage"
            :disabled="!inputMessage.trim()"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div class="chat-sidebar">
      <div class="sidebar-section card">
        <h4>Example Prompts</h4>
        <div class="prompt-list">
          <button
            v-for="prompt in examplePrompts"
            :key="prompt"
            class="prompt-btn"
            @click="usePrompt(prompt)"
          >
            {{ prompt }}
          </button>
        </div>
      </div>

      <div class="sidebar-section card" v-if="health">
        <h4>System Status</h4>
        <div class="status-list">
          <div class="status-item">
            <span class="status-label">LLM Provider</span>
            <span class="status-value" :class="isHealthy ? 'online' : 'offline'">
              {{ health.provider ? health.provider.charAt(0).toUpperCase() + health.provider.slice(1) : 'Unknown' }}
              ({{ isHealthy ? 'Online' : 'Offline' }})
            </span>
          </div>
          <div class="status-item" v-if="health.available_models?.length">
            <span class="status-label">Model</span>
            <span class="status-value">{{ health.available_models[0] }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Knowledge Base</span>
            <span class="status-value">{{ health.knowledge_base_documents || 0 }} docs</span>
          </div>
          <div class="status-item">
            <span class="status-label">RAG Enabled</span>
            <span class="status-value">{{ useRag ? 'Yes' : 'No' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Home Created Notification -->
    <Teleport to="body">
      <Transition name="notification">
        <div v-if="showHomeCreatedNotification && createdHomeInfo" class="notification-overlay">
          <div class="notification-card">
            <div class="notification-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
              </svg>
            </div>
            <div class="notification-content">
              <h3>Home Created Successfully!</h3>
              <p class="notification-name">{{ createdHomeInfo.name }}</p>
              <div class="notification-stats">
                <span class="stat">
                  <strong>{{ createdHomeInfo.total_rooms }}</strong> rooms
                </span>
                <span class="stat">
                  <strong>{{ createdHomeInfo.total_devices }}</strong> devices
                </span>
                <span class="stat">
                  <strong>{{ createdHomeInfo.total_inhabitants }}</strong> inhabitants
                </span>
              </div>
            </div>
            <div class="notification-actions">
              <button class="btn btn-primary" @click="goToHomeBuilder">
                View in Home Builder
              </button>
              <button class="btn btn-ghost" @click="dismissHomeNotification">
                Dismiss
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Threat Created Notification -->
    <Teleport to="body">
      <Transition name="notification">
        <div v-if="showThreatCreatedNotification && createdThreatInfo" class="notification-overlay">
          <div class="notification-card threat-card">
            <div class="notification-icon threat-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            </div>
            <div class="notification-content">
              <h3>Threat Scenario Created!</h3>
              <p class="notification-name">{{ createdThreatInfo.name }}</p>
              <div class="notification-stats">
                <span class="stat">
                  <strong class="threat-severity" :class="createdThreatInfo.severity">{{ createdThreatInfo.severity }}</strong> severity
                </span>
                <span class="stat">
                  <strong>{{ createdThreatInfo.category }}</strong> category
                </span>
                <span class="stat">
                  <strong>{{ createdThreatInfo.target_device_types?.length || 0 }}</strong> targets
                </span>
              </div>
              <p class="notification-description">{{ createdThreatInfo.description?.substring(0, 100) }}{{ createdThreatInfo.description?.length > 100 ? '...' : '' }}</p>
            </div>
            <div class="notification-actions">
              <button class="btn btn-primary" @click="goToThreatBuilder">
                View in Threat Builder
              </button>
              <button class="btn btn-ghost" @click="dismissThreatNotification">
                Dismiss
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Scenario Created Notification (composite home + threat) -->
    <Teleport to="body">
      <Transition name="notification">
        <div v-if="showScenarioCreatedNotification && createdScenarioInfo" class="notification-overlay">
          <div class="notification-card scenario-card">
            <div class="notification-icon scenario-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polygon points="10 8 16 12 10 16 10 8"></polygon>
              </svg>
            </div>
            <div class="notification-content">
              <h3>Scenario Ready to Simulate!</h3>
              <p class="notification-name">{{ createdScenarioInfo.scenario.name }}</p>
              <div class="notification-stats">
                <span class="stat" v-if="createdScenarioInfo.home">
                  <strong>{{ createdScenarioInfo.home.total_rooms }}</strong> rooms
                </span>
                <span class="stat" v-if="createdScenarioInfo.home">
                  <strong>{{ createdScenarioInfo.home.total_devices }}</strong> devices
                </span>
                <span class="stat" v-if="createdScenarioInfo.threat">
                  <strong class="threat-severity" :class="createdScenarioInfo.threat.severity">{{ createdScenarioInfo.threat.severity }}</strong> threat
                </span>
              </div>
              <p class="notification-description" v-if="createdScenarioInfo.threat">
                Threat: {{ createdScenarioInfo.threat.name }}
              </p>
            </div>
            <div class="notification-actions">
              <button class="btn btn-primary scenario-btn" @click="goToSimulation">
                Start Simulation
              </button>
              <button class="btn btn-ghost" @click="dismissScenarioNotification">
                Dismiss
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script lang="ts">
const examplePrompts = [
  // Knowledge & Learning
  "What are common IoT security vulnerabilities?",
  "Explain the MITRE ATT&CK framework for IoT",
  "How does a man-in-the-middle attack work on smart home devices?",
  // Home Building Actions
  "Build a modern smart home with 5 rooms",
  "Create a small apartment with security cameras",
  "Build a family home with smart thermostats and lighting",
  // Threat Building Actions
  "Create a data exfiltration attack scenario",
  "Build a ransomware threat targeting smart locks",
  "Create a botnet recruitment attack for IoT devices",
  // Analysis & Detection
  "How can I detect anomalies in smart home network traffic?",
  "What are the indicators of a compromised smart device?",
]

function formatMessage(content: string): string {
  if (!content) return ''

  // Basic markdown-like formatting
  let formatted = content
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Line breaks
    .replace(/\n/g, '<br>')
    // Citations [Source N]
    .replace(/\[Source (\d+)\]/g, '<span class="citation">[Source $1]</span>')

  return formatted
}

export default {
  methods: {
    formatMessage
  }
}
</script>

<style scoped>
.chat-view {
  display: grid;
  grid-template-columns: 1fr 280px;
  grid-template-rows: auto 1fr;
  gap: var(--spacing-lg);
  height: calc(100vh - 180px);
  min-height: 500px;
}

.chat-view:has(.history-panel) {
  grid-template-columns: 240px 1fr 280px;
}

.history-panel {
  grid-row: 2;
  grid-column: 1;
  padding: 0;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.chat-container.with-history {
  grid-column: 2;
}

.chat-header {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-title h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.chat-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.message {
  display: flex;
  gap: var(--spacing-md);
  max-width: 85%;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--bg-input);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.875rem;
}

.message.user .message-avatar {
  background: var(--color-primary);
  color: var(--bg-dark);
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.message-content {
  padding: var(--spacing-md);
  border-radius: var(--radius-lg);
  background: var(--bg-input);
  line-height: 1.6;
}

.message.user .message-content {
  background: var(--color-primary);
  color: var(--bg-dark);
}

.message-content.streaming {
  position: relative;
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background: var(--color-primary);
  margin-left: 2px;
  animation: blink 1s infinite;
  vertical-align: text-bottom;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.message-content.loading {
  display: flex;
  gap: 6px;
  padding: var(--spacing-md) var(--spacing-lg);
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--text-secondary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.message-sources {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  align-items: center;
  font-size: 0.75rem;
}

.sources-label {
  color: var(--text-muted);
}

.source-tag {
  background: var(--bg-hover);
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
}

.message-meta {
  font-size: 0.75rem;
}

.confidence {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.confidence.high {
  background: rgba(34, 197, 94, 0.2);
  color: var(--color-success);
}

.confidence.medium {
  background: rgba(245, 158, 11, 0.2);
  color: var(--color-warning);
}

.confidence.low {
  background: rgba(239, 68, 68, 0.2);
  color: var(--color-error);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  color: var(--text-muted);
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(239, 68, 68, 0.1);
  border-top: 1px solid var(--color-error);
  color: var(--color-error);
  font-size: 0.875rem;
}

.error-banner span {
  flex: 1;
}

.input-area {
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.input-options {
  display: flex;
  gap: var(--spacing-md);
}

.toggle-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.toggle-option input {
  accent-color: var(--color-primary);
}

.toggle-option.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-label {
  user-select: none;
}

.input-row {
  display: flex;
  gap: var(--spacing-sm);
}

.input-row .input {
  flex: 1;
}

.input-row .btn {
  padding: var(--spacing-sm) var(--spacing-md);
}

.btn-stop {
  background: var(--color-error);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-stop:hover {
  background: #dc2626;
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  overflow-y: auto;
}

.sidebar-section {
  padding: var(--spacing-md);
}

.sidebar-section h4 {
  margin-bottom: var(--spacing-sm);
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.prompt-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.prompt-btn {
  text-align: left;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.prompt-btn:hover {
  background: var(--bg-hover);
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}

.status-label {
  color: var(--text-muted);
}

.status-value {
  color: var(--text-secondary);
}

.status-value.online {
  color: var(--color-success);
}

.status-value.offline {
  color: var(--color-error);
}

/* Citation styling */
:deep(.citation) {
  background: var(--bg-hover);
  color: var(--color-primary);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.8em;
  font-weight: 500;
}

/* Responsive */
@media (max-width: 900px) {
  .chat-view {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-view:has(.history-panel) {
    grid-template-columns: 1fr;
  }

  .chat-header {
    grid-column: 1;
  }

  .history-panel {
    grid-column: 1;
    height: 200px;
  }

  .chat-container {
    height: 60vh;
    min-height: 400px;
    grid-column: 1;
  }

  .chat-container.with-history {
    grid-column: 1;
  }

  .chat-sidebar {
    display: none;
  }
}

/* Notification overlay styles - using :global for Teleport */
:global(.notification-overlay) {
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
  backdrop-filter: blur(4px);
}

:global(.notification-card) {
  background: var(--bg-card, #1e1e2e);
  border-radius: 12px;
  padding: 32px;
  max-width: 420px;
  width: 90%;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  animation: popIn 0.3s ease;
}

@keyframes popIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

:global(.notification-icon) {
  width: 64px;
  height: 64px;
  background: rgba(34, 197, 94, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  color: #22c55e;
}

:global(.notification-content h3) {
  color: var(--text-primary, #fff);
  margin: 0 0 8px;
  font-size: 1.25rem;
}

:global(.notification-name) {
  color: var(--text-secondary, #a0a0a0);
  margin: 0 0 16px;
  font-size: 0.9rem;
}

:global(.notification-stats) {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-bottom: 24px;
}

:global(.notification-stats .stat) {
  color: var(--text-secondary, #a0a0a0);
  font-size: 0.875rem;
}

:global(.notification-stats .stat strong) {
  color: var(--color-primary, #6366f1);
  font-size: 1.25rem;
  display: block;
}

:global(.notification-actions) {
  display: flex;
  gap: 12px;
  justify-content: center;
}

:global(.notification-actions .btn) {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

:global(.notification-actions .btn-primary) {
  background: var(--color-primary, #6366f1);
  color: white;
  border: none;
}

:global(.notification-actions .btn-primary:hover) {
  background: #4f46e5;
}

:global(.notification-actions .btn-ghost) {
  background: transparent;
  color: var(--text-secondary, #a0a0a0);
  border: 1px solid var(--border-color, #333);
}

:global(.notification-actions .btn-ghost:hover) {
  background: var(--bg-hover, #2a2a3a);
}

/* Notification transitions */
:global(.notification-enter-active),
:global(.notification-leave-active) {
  transition: all 0.3s ease;
}

:global(.notification-enter-from),
:global(.notification-leave-to) {
  opacity: 0;
}

:global(.notification-enter-from .notification-card),
:global(.notification-leave-to .notification-card) {
  transform: scale(0.9);
}

/* Threat notification specific styles */
:global(.notification-card.threat-card) {
  max-width: 480px;
}

:global(.notification-icon.threat-icon) {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

:global(.notification-description) {
  color: var(--text-muted, #888);
  font-size: 0.8rem;
  margin: 0 0 16px;
  line-height: 1.5;
  text-align: left;
  padding: 12px;
  background: var(--bg-input, #2a2a3a);
  border-radius: 8px;
}

:global(.threat-severity) {
  text-transform: uppercase;
  font-size: 0.9rem !important;
}

:global(.threat-severity.critical) {
  color: #dc2626 !important;
}

:global(.threat-severity.high) {
  color: #ef4444 !important;
}

:global(.threat-severity.medium) {
  color: #f59e0b !important;
}

:global(.threat-severity.low) {
  color: #22c55e !important;
}

/* Scenario notification specific styles */
:global(.notification-card.scenario-card) {
  max-width: 500px;
}

:global(.notification-icon.scenario-icon) {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

:global(.scenario-btn) {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

:global(.scenario-btn:hover) {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
}
</style>
