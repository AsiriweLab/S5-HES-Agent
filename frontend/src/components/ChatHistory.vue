<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const sessions = computed(() => chatStore.sessions)
const currentSessionId = computed(() => chatStore.currentSessionId)

function selectSession(sessionId: string) {
  chatStore.selectSession(sessionId)
}

function deleteSession(sessionId: string, event: Event) {
  event.stopPropagation()
  if (confirm('Delete this conversation?')) {
    chatStore.deleteSession(sessionId)
  }
}

function createNewSession() {
  chatStore.createSession()
}

function formatDate(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return 'Today'
  } else if (days === 1) {
    return 'Yesterday'
  } else if (days < 7) {
    return `${days} days ago`
  } else {
    return date.toLocaleDateString()
  }
}

function truncateTitle(title: string, maxLength: number = 30): string {
  if (title.length <= maxLength) return title
  return title.substring(0, maxLength) + '...'
}
</script>

<template>
  <div class="chat-history">
    <div class="history-header">
      <h4>Conversations</h4>
      <button class="btn btn-ghost btn-icon" @click="createNewSession" title="New conversation">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      </button>
    </div>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === currentSessionId }"
        @click="selectSession(session.id)"
      >
        <div class="session-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <div class="session-info">
          <span class="session-title">{{ truncateTitle(session.title) }}</span>
          <span class="session-date">{{ formatDate(session.updatedAt) }}</span>
        </div>
        <button
          class="delete-btn btn btn-ghost btn-icon"
          @click="deleteSession(session.id, $event)"
          title="Delete conversation"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>

      <div v-if="sessions.length === 0" class="empty-state">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <p>No conversations yet</p>
        <button class="btn btn-primary btn-sm" @click="createNewSession">
          Start a conversation
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-history {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.history-header h4 {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color var(--transition-fast);
  margin-bottom: var(--spacing-xs);
}

.session-item:hover {
  background: var(--bg-hover);
}

.session-item.active {
  background: var(--bg-hover);
  border-left: 2px solid var(--color-primary);
}

.session-icon {
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.session-title {
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.delete-btn {
  opacity: 0;
  color: var(--text-muted);
  padding: var(--spacing-xs);
  transition: opacity var(--transition-fast), color var(--transition-fast);
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--color-error);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
  text-align: center;
  gap: var(--spacing-sm);
}

.empty-state p {
  margin: 0;
  font-size: 0.875rem;
}
</style>
