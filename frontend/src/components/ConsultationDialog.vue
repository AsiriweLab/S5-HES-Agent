<script setup lang="ts">
import { computed } from 'vue'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()

const isVisible = computed(() => modeStore.showConsultationDialog)
const consultation = computed(() => modeStore.currentConsultation)
const isLoading = computed(() => modeStore.isLoading)
const error = computed(() => modeStore.error)

// Response is now included directly from the API consultation response
const aiResponse = computed(() => consultation.value?.response || '')

function getConfidenceColor(score?: number): string {
  if (!score) return 'var(--text-muted)'
  if (score >= 0.8) return 'var(--success, #059669)'
  if (score >= 0.5) return 'var(--warning, #d97706)'
  return 'var(--danger, #dc2626)'
}

function acceptResponse() {
  if (consultation.value) {
    modeStore.acceptConsultation(consultation.value.id, aiResponse.value)
  }
}

function rejectResponse() {
  if (consultation.value) {
    modeStore.rejectConsultation(consultation.value.id)
  }
}

function close() {
  modeStore.closeConsultationDialog()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isVisible" class="dialog-overlay" @click.self="close">
      <div class="dialog">
        <div class="dialog-header">
          <h3>Expert Consultation</h3>
          <button class="btn btn-ghost btn-icon" @click="close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="dialog-body">
          <!-- User Question -->
          <div class="section">
            <h4>Your Question</h4>
            <div class="question-box">
              {{ consultation?.question }}
            </div>
          </div>

          <!-- AI Response -->
          <div class="section">
            <h4>AI Expert Response</h4>

            <div v-if="isLoading" class="loading-state">
              <div class="spinner"></div>
              <span>Getting expert advice...</span>
            </div>

            <div v-else-if="error" class="error-state">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>{{ error }}</span>
            </div>

            <div v-else class="response-box markdown-content">
              {{ aiResponse }}
            </div>
          </div>

          <!-- Confidence & Metadata -->
          <div v-if="consultation && !isLoading" class="meta-section">
            <div class="meta-grid">
              <div class="meta-item">
                <span class="meta-label">Confidence</span>
                <span class="meta-value" :style="{ color: getConfidenceColor(consultation.confidenceScore) }">
                  {{ consultation.confidence || 'Unknown' }}
                  <span v-if="consultation.confidenceScore">({{ (consultation.confidenceScore * 100).toFixed(0) }}%)</span>
                </span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Status</span>
                <span :class="['status-badge', consultation.status]">{{ consultation.status }}</span>
              </div>
            </div>

            <!-- Sources -->
            <div v-if="consultation.sources && consultation.sources.length > 0" class="sources-section">
              <h4>Sources</h4>
              <ul class="sources-list">
                <li v-for="(source, idx) in consultation.sources" :key="idx">{{ source }}</li>
              </ul>
            </div>

            <!-- Verification Notes -->
            <div v-if="consultation.verificationNotes && consultation.verificationNotes.length > 0" class="verification-section">
              <h4>Verification Notes</h4>
              <ul class="verification-list">
                <li v-for="(note, idx) in consultation.verificationNotes" :key="idx">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                  {{ note }}
                </li>
              </ul>
            </div>
          </div>

          <!-- Decision Prompt -->
          <div class="decision-section">
            <p class="decision-prompt">
              Do you want to apply this suggestion?
            </p>
            <div class="decision-buttons">
              <button
                class="btn btn-ghost reject-btn"
                @click="rejectResponse"
                :disabled="isLoading"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                Reject
              </button>
              <button
                class="btn btn-primary accept-btn"
                @click="acceptResponse"
                :disabled="isLoading || !aiResponse"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Accept
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.dialog {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.2s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.dialog-header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.dialog-body {
  padding: var(--spacing-lg);
  overflow-y: auto;
  flex: 1;
}

.section {
  margin-bottom: var(--spacing-lg);
}

.section h4 {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.question-box {
  background: var(--bg-input);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  color: var(--text-primary);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  color: var(--text-secondary);
}

.error-state {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(239, 68, 68, 0.1);
  border-radius: var(--radius-md);
  color: var(--color-error);
}

.error-state button {
  margin-left: auto;
}

.response-box {
  background: var(--bg-input);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.decision-section {
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-lg);
  margin-top: var(--spacing-md);
}

.decision-prompt {
  text-align: center;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.decision-buttons {
  display: flex;
  justify-content: center;
  gap: var(--spacing-md);
}

.reject-btn {
  color: var(--color-error);
}

.reject-btn:hover {
  background: rgba(239, 68, 68, 0.1);
}

.accept-btn {
  min-width: 120px;
}

/* Metadata Section */
.meta-section {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.meta-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.meta-value {
  font-weight: 600;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  text-transform: uppercase;
}

.status-badge.pending {
  background: rgba(217, 119, 6, 0.1);
  color: #d97706;
}

.status-badge.accepted {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
}

.status-badge.rejected {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.sources-section,
.verification-section {
  margin-top: var(--spacing-md);
}

.sources-section h4,
.verification-section h4 {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: var(--spacing-xs);
}

.sources-list,
.verification-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.sources-list li {
  padding: var(--spacing-xs) 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.sources-list li::before {
  content: "• ";
  color: var(--color-primary);
}

.verification-list li {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.verification-list li svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--color-primary);
}
</style>
