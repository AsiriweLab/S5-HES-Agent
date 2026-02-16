<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  reviewApi,
  type ReviewItem,
  type ReviewQueueStats,
  type ReviewQueueSettings,
  type ReviewDecision,
  type ReviewItemStatus,
} from '@/services/reviewApi'

// State
const isLoading = ref(false)
const isApiAvailable = ref(false)
const pendingItems = ref<ReviewItem[]>([])
const reviewedItems = ref<ReviewItem[]>([])
const stats = ref<ReviewQueueStats | null>(null)
const settings = ref<ReviewQueueSettings | null>(null)
const selectedItem = ref<ReviewItem | null>(null)
const activeTab = ref<'pending' | 'reviewed' | 'settings'>('pending')
const reviewNotes = ref('')
const showSettingsModal = ref(false)

// Computed
const pendingCount = computed(() => stats.value?.pending_items ?? pendingItems.value.length)

// Polling
let pollingInterval: ReturnType<typeof setInterval> | null = null

// Methods
function getConfidenceColor(score: number): string {
  if (score >= 0.85) return '#22c55e'
  if (score >= 0.7) return '#eab308'
  if (score >= 0.5) return '#f97316'
  return '#dc2626'
}

function getStatusColor(status: ReviewItemStatus): string {
  const colors: Record<ReviewItemStatus, string> = {
    pending: '#eab308',
    approved: '#22c55e',
    rejected: '#dc2626',
    modified: '#3b82f6',
  }
  return colors[status]
}

function getItemTypeIcon(type: string): string {
  const icons: Record<string, string> = {
    llm_response: '💬',
    agent_output: '🤖',
    rag_result: '📚',
    home_config: '🏠',
    threat_scenario: '⚠️',
    simulation_result: '📊',
  }
  return icons[type] || '📄'
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadData() {
  if (!isApiAvailable.value) return

  try {
    const [itemsData, statsData, reviewedData] = await Promise.all([
      reviewApi.getQueue(20),
      reviewApi.getStats(),
      reviewApi.getReviewedItems(20),
    ])
    pendingItems.value = itemsData
    stats.value = statsData
    reviewedItems.value = reviewedData
  } catch (error) {
    console.error('Failed to load review queue data:', error)
  }
}

async function loadSettings() {
  try {
    settings.value = await reviewApi.getSettings()
  } catch (error) {
    console.error('Failed to load settings:', error)
  }
}

async function submitReview(decision: 'approved' | 'rejected' | 'modified') {
  if (!selectedItem.value) return

  isLoading.value = true
  try {
    const reviewDecision: ReviewDecision = {
      decision: decision as ReviewItemStatus,
      notes: reviewNotes.value || undefined,
    }

    await reviewApi.submitReview(selectedItem.value.item_id, reviewDecision)

    // Refresh data
    await loadData()

    // Clear selection
    selectedItem.value = null
    reviewNotes.value = ''
  } catch (error) {
    console.error('Failed to submit review:', error)
  } finally {
    isLoading.value = false
  }
}

async function saveSettings() {
  if (!settings.value) return

  try {
    await reviewApi.updateSettings(settings.value)
    showSettingsModal.value = false
  } catch (error) {
    console.error('Failed to save settings:', error)
  }
}

async function addSampleItem() {
  try {
    await reviewApi.addSampleItem()
    await loadData()
  } catch (error) {
    console.error('Failed to add sample item:', error)
  }
}

async function clearReviewedHistory() {
  try {
    await reviewApi.clearReviewedItems()
    await loadData()
  } catch (error) {
    console.error('Failed to clear history:', error)
  }
}

function selectItem(item: ReviewItem) {
  selectedItem.value = selectedItem.value?.item_id === item.item_id ? null : item
  reviewNotes.value = ''
}

function startPolling(interval: number = 5000) {
  stopPolling()
  pollingInterval = setInterval(loadData, interval)
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
}

// Lifecycle
onMounted(async () => {
  isLoading.value = true
  try {
    isApiAvailable.value = await reviewApi.checkAvailability()
    if (isApiAvailable.value) {
      await Promise.all([loadData(), loadSettings()])
      startPolling(5000)
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
  <div class="review-queue">
    <!-- Header -->
    <div class="queue-header">
      <div class="header-title">
        <h2>Human Review Queue</h2>
        <span class="badge" :class="{ active: pendingCount > 0 }">
          {{ pendingCount }} pending
        </span>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost btn-sm" @click="addSampleItem" title="Add sample item for testing">
          + Test Item
        </button>
        <button class="btn btn-ghost btn-sm" @click="showSettingsModal = true">
          Settings
        </button>
      </div>
    </div>

    <!-- API Unavailable -->
    <div v-if="!isApiAvailable && !isLoading" class="api-unavailable">
      <div class="unavailable-icon">🔒</div>
      <h3>Review Queue API Unavailable</h3>
      <p>The review queue connects to the backend verification system.</p>
      <p class="note">Ensure the backend server is running on port 8000.</p>
    </div>

    <!-- Loading -->
    <div v-else-if="isLoading" class="loading">
      <div class="spinner"></div>
      <p>Loading review queue...</p>
    </div>

    <!-- Main Content -->
    <div v-else class="queue-content">
      <!-- Stats Bar -->
      <div v-if="stats" class="stats-bar">
        <div class="stat">
          <span class="stat-value">{{ stats.total_items }}</span>
          <span class="stat-label">Total</span>
        </div>
        <div class="stat">
          <span class="stat-value" style="color: #eab308">{{ stats.pending_items }}</span>
          <span class="stat-label">Pending</span>
        </div>
        <div class="stat">
          <span class="stat-value" style="color: #22c55e">{{ stats.approved_items }}</span>
          <span class="stat-label">Approved</span>
        </div>
        <div class="stat">
          <span class="stat-value" style="color: #dc2626">{{ stats.rejected_items }}</span>
          <span class="stat-label">Rejected</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ (stats.avg_confidence * 100).toFixed(0) }}%</span>
          <span class="stat-label">Avg Conf.</span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: activeTab === 'pending' }"
          @click="activeTab = 'pending'"
        >
          Pending ({{ pendingItems.length }})
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'reviewed' }"
          @click="activeTab = 'reviewed'"
        >
          Reviewed ({{ reviewedItems.length }})
        </button>
      </div>

      <!-- Item List -->
      <div class="item-list">
        <template v-if="activeTab === 'pending'">
          <div v-if="pendingItems.length === 0" class="empty-state">
            <div class="empty-icon">✓</div>
            <p>No items pending review</p>
            <p class="empty-desc">All AI outputs are passing verification or being auto-handled.</p>
          </div>

          <div
            v-for="item in pendingItems"
            :key="item.item_id"
            class="review-item"
            :class="{ selected: selectedItem?.item_id === item.item_id }"
            @click="selectItem(item)"
          >
            <div class="item-header">
              <span class="item-type">{{ getItemTypeIcon(item.item_type) }} {{ item.item_type.replace('_', ' ') }}</span>
              <div
                class="confidence-badge"
                :style="{ backgroundColor: getConfidenceColor(item.confidence_score) + '20', color: getConfidenceColor(item.confidence_score) }"
              >
                {{ (item.confidence_score * 100).toFixed(0) }}%
              </div>
            </div>
            <div class="item-summary">{{ item.content_summary }}</div>
            <div class="item-meta">
              <span class="meta-item">{{ formatDate(item.created_at) }}</span>
              <span class="meta-item" v-if="item.source_agent">{{ item.source_agent }}</span>
            </div>
            <div class="item-reasons" v-if="item.review_reasons.length > 0">
              <span class="reason" v-for="reason in item.review_reasons.slice(0, 2)" :key="reason">
                {{ reason }}
              </span>
            </div>
          </div>
        </template>

        <template v-else>
          <div v-if="reviewedItems.length === 0" class="empty-state">
            <div class="empty-icon">📋</div>
            <p>No reviewed items</p>
          </div>

          <div
            v-for="item in reviewedItems"
            :key="item.item_id"
            class="review-item reviewed"
            @click="selectItem(item)"
          >
            <div class="item-header">
              <span class="item-type">{{ getItemTypeIcon(item.item_type) }} {{ item.item_type.replace('_', ' ') }}</span>
              <div
                class="status-badge"
                :style="{ backgroundColor: getStatusColor(item.status) + '20', color: getStatusColor(item.status) }"
              >
                {{ item.status }}
              </div>
            </div>
            <div class="item-summary">{{ item.content_summary }}</div>
            <div class="item-meta">
              <span class="meta-item">Reviewed: {{ formatDate(item.reviewed_at || '') }}</span>
              <span class="meta-item" v-if="item.reviewer_notes">Note: {{ item.reviewer_notes }}</span>
            </div>
          </div>

          <button v-if="reviewedItems.length > 0" class="btn btn-ghost btn-sm clear-btn" @click="clearReviewedHistory">
            Clear History
          </button>
        </template>
      </div>

      <!-- Review Panel -->
      <div v-if="selectedItem && selectedItem.status === 'pending'" class="review-panel">
        <h3>Review Item</h3>
        <div class="detail-grid">
          <div class="detail-item">
            <label>Type</label>
            <span>{{ selectedItem.item_type }}</span>
          </div>
          <div class="detail-item">
            <label>Confidence</label>
            <span :style="{ color: getConfidenceColor(selectedItem.confidence_score) }">
              {{ (selectedItem.confidence_score * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="detail-item" v-if="selectedItem.source_agent">
            <label>Source Agent</label>
            <span>{{ selectedItem.source_agent }}</span>
          </div>
        </div>

        <div class="flagged-checks" v-if="selectedItem.flagged_checks.length > 0">
          <h4>Flagged Checks</h4>
          <div v-for="check in selectedItem.flagged_checks" :key="check.name" class="check-item">
            <div class="check-header">
              <span class="check-category">{{ check.category }}</span>
              <span class="check-confidence">{{ (check.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div class="check-message">{{ check.message }}</div>
          </div>
        </div>

        <div class="content-preview">
          <h4>Content</h4>
          <pre>{{ JSON.stringify(selectedItem.content, null, 2) }}</pre>
        </div>

        <div class="review-form">
          <textarea
            v-model="reviewNotes"
            placeholder="Add reviewer notes (optional)"
            rows="2"
          ></textarea>
          <div class="review-actions">
            <button class="btn btn-success" @click="submitReview('approved')" :disabled="isLoading">
              Approve
            </button>
            <button class="btn btn-error" @click="submitReview('rejected')" :disabled="isLoading">
              Reject
            </button>
            <button class="btn btn-secondary" @click="selectedItem = null">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Settings Modal -->
    <div v-if="showSettingsModal && settings" class="modal-overlay" @click.self="showSettingsModal = false">
      <div class="modal">
        <h3>Review Queue Settings</h3>

        <div class="setting-item">
          <label>Auto-Approve Threshold</label>
          <span class="setting-desc">Items with confidence >= {{ (settings.auto_approve_threshold * 100).toFixed(0) }}% are auto-approved</span>
          <input type="range" min="0.5" max="1" step="0.05" v-model.number="settings.auto_approve_threshold" />
        </div>

        <div class="setting-item">
          <label>Auto-Reject Threshold</label>
          <span class="setting-desc">Items with confidence &lt; {{ (settings.auto_reject_threshold * 100).toFixed(0) }}% are auto-rejected</span>
          <input type="range" min="0.3" max="0.7" step="0.05" v-model.number="settings.auto_reject_threshold" />
        </div>

        <div class="setting-item">
          <label>Strict Mode</label>
          <span class="setting-desc">Require review for ALL items (no auto-approve)</span>
          <input type="checkbox" v-model="settings.strict_mode" />
        </div>

        <div class="modal-actions">
          <button class="btn btn-primary" @click="saveSettings">Save Settings</button>
          <button class="btn btn-ghost" @click="showSettingsModal = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.review-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.queue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-title h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-input);
  color: var(--text-muted);
}

.badge.active {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.api-unavailable,
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  min-height: 200px;
}

.unavailable-icon,
.empty-icon {
  font-size: 2rem;
  margin-bottom: var(--spacing-md);
}

.api-unavailable h3,
.empty-state p:first-of-type {
  margin: 0 0 var(--spacing-xs);
  color: var(--text-primary);
}

.api-unavailable p,
.empty-desc,
.note {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.note {
  font-style: italic;
  color: var(--text-muted);
}

.queue-content {
  padding: var(--spacing-md);
}

.stats-bar {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.tabs {
  display: flex;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-md);
}

.tab {
  background: none;
  border: none;
  padding: var(--spacing-xs) var(--spacing-md);
  font-size: 0.85rem;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  max-height: 400px;
  overflow-y: auto;
}

.review-item {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.review-item:hover {
  border-color: var(--border-color);
}

.review-item.selected {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.05);
}

.review-item.reviewed {
  opacity: 0.8;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.item-type {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.confidence-badge,
.status-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 600;
}

.item-summary {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.4;
  margin-bottom: var(--spacing-xs);
}

.item-meta {
  display: flex;
  gap: var(--spacing-md);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.item-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}

.reason {
  font-size: 0.65rem;
  padding: 1px 6px;
  background: rgba(234, 179, 8, 0.1);
  color: #d97706;
  border-radius: var(--radius-sm);
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
}

.clear-btn {
  margin-top: var(--spacing-md);
  align-self: center;
}

.review-panel {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.review-panel h3 {
  margin: 0 0 var(--spacing-md);
  font-size: 0.9rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.detail-item label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.detail-item span {
  font-size: 0.85rem;
  color: var(--text-primary);
}

.flagged-checks {
  margin-bottom: var(--spacing-md);
}

.flagged-checks h4 {
  font-size: 0.8rem;
  margin: 0 0 var(--spacing-sm);
  color: var(--text-secondary);
}

.check-item {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-xs);
}

.check-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
}

.check-category {
  color: var(--text-muted);
  text-transform: uppercase;
}

.check-confidence {
  color: #f97316;
}

.check-message {
  font-size: 0.8rem;
  color: var(--text-primary);
  margin-top: 2px;
}

.content-preview {
  margin-bottom: var(--spacing-md);
}

.content-preview h4 {
  font-size: 0.8rem;
  margin: 0 0 var(--spacing-xs);
  color: var(--text-secondary);
}

.content-preview pre {
  font-size: 0.75rem;
  background: var(--bg-input);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  max-height: 150px;
  overflow: auto;
  color: var(--text-secondary);
}

.review-form textarea {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.85rem;
  resize: vertical;
  margin-bottom: var(--spacing-sm);
}

.review-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.btn-success {
  background: #22c55e;
  color: white;
}

.btn-error {
  background: #dc2626;
  color: white;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  width: 90%;
  max-width: 400px;
}

.modal h3 {
  margin: 0 0 var(--spacing-lg);
}

.setting-item {
  margin-bottom: var(--spacing-md);
}

.setting-item label {
  display: block;
  font-weight: 500;
  margin-bottom: 2px;
  color: var(--text-primary);
}

.setting-desc {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.setting-item input[type="range"] {
  width: 100%;
}

.setting-item input[type="checkbox"] {
  width: 20px;
  height: 20px;
}

.modal-actions {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
