<script setup lang="ts">
import { computed } from 'vue'

export interface DeviceAction {
  id: string
  type: 'device_control' | 'device_config' | 'scene_activate' | 'automation_trigger'
  deviceId?: string
  deviceName: string
  deviceType: string
  action: string
  parameters?: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected' | 'executing' | 'completed' | 'failed'
  timestamp: Date
}

const props = defineProps<{
  actions: DeviceAction[]
}>()

const emit = defineEmits<{
  confirm: [actionId: string]
  reject: [actionId: string]
  confirmAll: []
  rejectAll: []
}>()

const pendingActions = computed(() =>
  props.actions.filter(a => a.status === 'pending')
)

const hasPendingActions = computed(() => pendingActions.value.length > 0)

function getDeviceIcon(deviceType: string): string {
  const icons: Record<string, string> = {
    light: '💡',
    thermostat: '🌡️',
    camera: '📷',
    lock: '🔒',
    sensor: '📡',
    switch: '🔌',
    speaker: '🔊',
    tv: '📺',
    blinds: '🪟',
    garage: '🚗',
    doorbell: '🔔',
    outlet: '⚡',
    fan: '🌀',
    alarm: '🚨',
  }
  return icons[deviceType.toLowerCase()] || '📟'
}

function getStatusClass(status: DeviceAction['status']): string {
  const classes: Record<DeviceAction['status'], string> = {
    pending: 'status-pending',
    confirmed: 'status-confirmed',
    rejected: 'status-rejected',
    executing: 'status-executing',
    completed: 'status-completed',
    failed: 'status-failed',
  }
  return classes[status]
}

function getStatusLabel(status: DeviceAction['status']): string {
  const labels: Record<DeviceAction['status'], string> = {
    pending: 'Awaiting Confirmation',
    confirmed: 'Confirmed',
    rejected: 'Rejected',
    executing: 'Executing...',
    completed: 'Completed',
    failed: 'Failed',
  }
  return labels[status]
}

function formatParameters(params?: Record<string, unknown>): string {
  if (!params || Object.keys(params).length === 0) return ''
  return Object.entries(params)
    .map(([key, value]) => `${key}: ${value}`)
    .join(', ')
}
</script>

<template>
  <div v-if="actions.length > 0" class="action-renderer">
    <div class="action-header">
      <div class="header-content">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        <h4>Suggested Actions</h4>
        <span class="action-count">{{ actions.length }} action{{ actions.length !== 1 ? 's' : '' }}</span>
      </div>

      <div v-if="hasPendingActions" class="bulk-actions">
        <button class="btn btn-ghost btn-sm" @click="emit('rejectAll')">
          Reject All
        </button>
        <button class="btn btn-primary btn-sm" @click="emit('confirmAll')">
          Confirm All
        </button>
      </div>
    </div>

    <div class="action-list">
      <div
        v-for="action in actions"
        :key="action.id"
        class="action-card"
        :class="getStatusClass(action.status)"
      >
        <div class="action-icon">
          {{ getDeviceIcon(action.deviceType) }}
        </div>

        <div class="action-content">
          <div class="action-main">
            <span class="device-name">{{ action.deviceName }}</span>
            <span class="action-arrow">→</span>
            <span class="action-name">{{ action.action }}</span>
          </div>

          <div v-if="formatParameters(action.parameters)" class="action-params">
            {{ formatParameters(action.parameters) }}
          </div>

          <div class="action-meta">
            <span class="device-type">{{ action.deviceType }}</span>
            <span class="status-badge" :class="getStatusClass(action.status)">
              {{ getStatusLabel(action.status) }}
            </span>
          </div>
        </div>

        <div v-if="action.status === 'pending'" class="action-buttons">
          <button
            class="btn btn-ghost btn-icon reject-btn"
            @click="emit('reject', action.id)"
            title="Reject action"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
          <button
            class="btn btn-primary btn-icon confirm-btn"
            @click="emit('confirm', action.id)"
            title="Confirm action"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </button>
        </div>

        <div v-else-if="action.status === 'executing'" class="action-status-icon">
          <div class="spinner"></div>
        </div>

        <div v-else-if="action.status === 'completed'" class="action-status-icon success">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>

        <div v-else-if="action.status === 'failed'" class="action-status-icon error">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.action-renderer {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin: var(--spacing-md) 0;
}

.action-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-bottom: 1px solid var(--border-color);
}

.header-content {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.header-content h4 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.action-count {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.bulk-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.action-list {
  padding: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.action-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  border-left: 3px solid transparent;
  transition: all var(--transition-fast);
}

.action-card.status-pending {
  border-left-color: var(--color-warning);
}

.action-card.status-confirmed,
.action-card.status-completed {
  border-left-color: var(--color-success);
}

.action-card.status-rejected,
.action-card.status-failed {
  border-left-color: var(--color-error);
  opacity: 0.7;
}

.action-card.status-executing {
  border-left-color: var(--color-primary);
}

.action-icon {
  font-size: 1.5rem;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.action-content {
  flex: 1;
  min-width: 0;
}

.action-main {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-weight: 500;
  color: var(--text-primary);
}

.action-arrow {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.action-name {
  color: var(--color-primary);
}

.action-params {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 2px;
  font-family: monospace;
}

.action-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xs);
}

.device-type {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.status-badge.status-pending {
  background: rgba(245, 158, 11, 0.1);
  color: var(--color-warning);
}

.status-badge.status-confirmed,
.status-badge.status-completed {
  background: rgba(16, 185, 129, 0.1);
  color: var(--color-success);
}

.status-badge.status-rejected,
.status-badge.status-failed {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-error);
}

.status-badge.status-executing {
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-primary);
}

.action-buttons {
  display: flex;
  gap: var(--spacing-xs);
}

.reject-btn:hover {
  color: var(--color-error);
  background: rgba(239, 68, 68, 0.1);
}

.confirm-btn {
  padding: var(--spacing-xs);
}

.action-status-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-status-icon.success {
  color: var(--color-success);
}

.action-status-icon.error {
  color: var(--color-error);
}

@media (max-width: 640px) {
  .action-header {
    flex-direction: column;
    gap: var(--spacing-sm);
    align-items: flex-start;
  }

  .bulk-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .action-main {
    flex-wrap: wrap;
  }
}
</style>
