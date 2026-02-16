<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

// Props
interface ThreatEvent {
  id: string
  type: string
  name: string
  startTime: number
  duration: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  severityValue: number
  difficulty: number
  targetDevices: string[]
  description: string
  attackVector: string
  indicators: string[]
  stageNumber?: number
  dependsOn?: string[]
  successProbability?: number
  isChainStart?: boolean
}

interface AttackChain {
  id: string
  name: string
  description: string
  color: string
  eventIds: string[]
}

const props = defineProps<{
  events: ThreatEvent[]
  chains: AttackChain[]
  selectedChain: AttackChain | null
}>()

const emit = defineEmits<{
  (e: 'update:chains', chains: AttackChain[]): void
  (e: 'update:selectedChain', chain: AttackChain | null): void
  (e: 'addEventToChain', event: ThreatEvent, chain: AttackChain): void
  (e: 'removeEventFromChain', eventId: string): void
  (e: 'createChain'): void
  (e: 'deleteChain', chainId: string): void
  (e: 'close'): void
}>()

// State
const canvasRef = ref<HTMLElement | null>(null)
const isDragging = ref(false)
const draggedEventId = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

// Node positions for visual layout
const nodePositions = ref<Record<string, { x: number; y: number }>>({})

// Colors for severity
const severityColors: Record<string, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#dc2626',
}

// Get events in the currently selected chain
const chainEvents = computed(() => {
  if (!props.selectedChain) return []
  return props.selectedChain.eventIds
    .map(id => props.events.find(e => e.id === id))
    .filter((e): e is ThreatEvent => e !== undefined)
})

// Get available events (not in any chain)
const availableEvents = computed(() => {
  const usedIds = new Set(props.chains.flatMap(c => c.eventIds))
  return props.events.filter(e => !usedIds.has(e.id))
})

// Initialize node positions when chain changes
watch(() => props.selectedChain, () => {
  if (props.selectedChain) {
    initializeNodePositions()
  }
}, { immediate: true })

function initializeNodePositions() {
  if (!props.selectedChain) return

  const events = chainEvents.value
  if (events.length === 0) return

  const startX = 100
  const startY = 150
  const gapX = 200
  const gapY = 120

  events.forEach((event, index) => {
    if (!nodePositions.value[event.id]) {
      // Arrange in a flowing pattern
      const row = Math.floor(index / 3)
      const col = index % 3
      nodePositions.value[event.id] = {
        x: startX + col * gapX,
        y: startY + row * gapY,
      }
    }
  })
}

// Calculate connection paths between nodes
const connections = computed(() => {
  if (!props.selectedChain) return []

  const conns: { from: { x: number; y: number }; to: { x: number; y: number }; color: string }[] = []
  const events = chainEvents.value

  for (let i = 1; i < events.length; i++) {
    const fromEvent = events[i - 1]
    const toEvent = events[i]

    const fromPos = nodePositions.value[fromEvent.id] || { x: 100, y: 100 }
    const toPos = nodePositions.value[toEvent.id] || { x: 300, y: 100 }

    conns.push({
      from: { x: fromPos.x + 80, y: fromPos.y + 40 }, // Right center of node
      to: { x: toPos.x, y: toPos.y + 40 }, // Left center of node
      color: props.selectedChain?.color || '#6366f1',
    })
  }

  return conns
})

// Calculate SVG path for curved connection
function getConnectionPath(from: { x: number; y: number }, to: { x: number; y: number }): string {
  const midX = (from.x + to.x) / 2
  return `M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`
}

// Drag handlers
function handleDragStart(event: MouseEvent, eventId: string) {
  if (!nodePositions.value[eventId]) return

  isDragging.value = true
  draggedEventId.value = eventId

  const pos = nodePositions.value[eventId]
  dragOffset.value = {
    x: event.clientX - pos.x,
    y: event.clientY - pos.y,
  }

  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
}

function handleDragMove(event: MouseEvent) {
  if (!isDragging.value || !draggedEventId.value) return

  const canvasRect = canvasRef.value?.getBoundingClientRect()
  if (!canvasRect) return

  const x = event.clientX - dragOffset.value.x
  const y = event.clientY - dragOffset.value.y

  // Clamp to canvas bounds
  nodePositions.value[draggedEventId.value] = {
    x: Math.max(10, Math.min(canvasRect.width - 180, x)),
    y: Math.max(10, Math.min(canvasRect.height - 90, y)),
  }
}

function handleDragEnd() {
  isDragging.value = false
  draggedEventId.value = null

  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
}

// Handle dropping an available event onto the chain
function handleAvailableEventDrop(event: ThreatEvent) {
  if (!props.selectedChain) return

  emit('addEventToChain', event, props.selectedChain)

  // Initialize position for new node
  nextTick(() => {
    const existingCount = chainEvents.value.length
    nodePositions.value[event.id] = {
      x: 100 + ((existingCount - 1) % 3) * 200,
      y: 150 + Math.floor((existingCount - 1) / 3) * 120,
    }
  })
}

// Calculate overall chain success probability
const chainSuccessProbability = computed(() => {
  if (chainEvents.value.length === 0) return 0

  let probability = 1
  chainEvents.value.forEach(event => {
    const eventProb = (event.successProbability || 80) / 100
    probability *= eventProb
  })

  return Math.round(probability * 100)
})

// Calculate total chain duration
const chainDuration = computed(() => {
  if (chainEvents.value.length === 0) return 0

  let total = 0
  chainEvents.value.forEach(event => {
    total += event.duration
  })
  return total
})

// Get threat icon
function getThreatIcon(type: string): string {
  const icons: Record<string, string> = {
    man_in_the_middle: '🕵️',
    denial_of_service: '🚫',
    replay_attack: '🔄',
    firmware_exploit: '🔧',
    credential_theft: '🔑',
    data_exfiltration: '📤',
    device_hijack: '🎮',
    botnet_recruit: '🤖',
    ransomware: '💰',
    side_channel: '📊',
    reconnaissance: '🔍',
    initial_access: '🚪',
    lateral_movement: '↔️',
    persistence: '🔗',
  }
  return icons[type] || '⚡'
}
</script>

<template>
  <div class="chain-builder">
    <!-- Header -->
    <div class="builder-header">
      <div class="header-title">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
        </svg>
        <h3>Attack Chain Builder</h3>
      </div>
      <button class="close-btn" @click="emit('close')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>

    <div class="builder-content">
      <!-- Chain Selector Sidebar -->
      <aside class="chain-sidebar">
        <div class="sidebar-section">
          <div class="section-header">
            <h4>Attack Chains</h4>
            <button class="btn btn-sm btn-ghost" @click="emit('createChain')" title="Create new chain">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
          </div>

          <div class="chain-list" v-if="chains.length > 0">
            <div
              v-for="chain in chains"
              :key="chain.id"
              class="chain-item"
              :class="{ selected: selectedChain?.id === chain.id }"
              :style="{ '--chain-color': chain.color }"
              @click="emit('update:selectedChain', chain)"
            >
              <span class="chain-color-dot" :style="{ backgroundColor: chain.color }"></span>
              <div class="chain-info">
                <span class="chain-name">{{ chain.name }}</span>
                <span class="chain-meta">{{ chain.eventIds.length }} stages</span>
              </div>
              <button
                class="chain-delete"
                @click.stop="emit('deleteChain', chain.id)"
                title="Delete chain"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
          </div>

          <div v-else class="empty-chains">
            <p>No attack chains yet</p>
            <button class="btn btn-primary btn-sm" @click="emit('createChain')">
              Create First Chain
            </button>
          </div>
        </div>

        <!-- Available Events -->
        <div class="sidebar-section" v-if="selectedChain">
          <h4>Available Events</h4>
          <div class="available-events" v-if="availableEvents.length > 0">
            <div
              v-for="event in availableEvents"
              :key="event.id"
              class="available-event"
              @click="handleAvailableEventDrop(event)"
            >
              <span class="event-icon">{{ getThreatIcon(event.type) }}</span>
              <div class="event-info">
                <span class="event-name">{{ event.name }}</span>
                <span class="event-type">{{ event.type.replace(/_/g, ' ') }}</span>
              </div>
              <button class="add-btn" title="Add to chain">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
            </div>
          </div>
          <p v-else class="no-events">All events are assigned to chains</p>
        </div>
      </aside>

      <!-- Chain Canvas -->
      <main class="chain-canvas-area">
        <div v-if="!selectedChain" class="no-chain-selected">
          <div class="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.5">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
            </svg>
            <h3>Select or Create an Attack Chain</h3>
            <p>Choose a chain from the sidebar or create a new one to start building your multi-stage attack scenario</p>
          </div>
        </div>

        <div v-else class="chain-canvas" ref="canvasRef">
          <!-- Chain Info Bar -->
          <div class="chain-info-bar">
            <div class="chain-title">
              <span class="chain-color-indicator" :style="{ backgroundColor: selectedChain.color }"></span>
              <input
                type="text"
                class="chain-name-edit"
                :value="selectedChain.name"
                @input="e => {
                  if (!selectedChain) return
                  const chainId = selectedChain.id
                  const updatedChains = chains.map(c =>
                    c.id === chainId ? { ...c, name: (e.target as HTMLInputElement).value } : c
                  )
                  emit('update:chains', updatedChains)
                }"
              />
            </div>
            <div class="chain-stats">
              <div class="stat">
                <span class="stat-label">Stages</span>
                <span class="stat-value">{{ chainEvents.length }}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Duration</span>
                <span class="stat-value">{{ chainDuration }}m</span>
              </div>
              <div class="stat">
                <span class="stat-label">Success Rate</span>
                <span class="stat-value" :class="chainSuccessProbability < 30 ? 'low' : chainSuccessProbability < 60 ? 'medium' : 'high'">
                  {{ chainSuccessProbability }}%
                </span>
              </div>
            </div>
          </div>

          <!-- SVG Connections -->
          <svg class="connections-svg">
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon :points="'0 0, 10 3.5, 0 7'" :fill="selectedChain.color" />
              </marker>
            </defs>
            <path
              v-for="(conn, idx) in connections"
              :key="idx"
              :d="getConnectionPath(conn.from, conn.to)"
              fill="none"
              :stroke="conn.color"
              stroke-width="3"
              stroke-dasharray="8,4"
              marker-end="url(#arrowhead)"
              class="connection-path"
            />
          </svg>

          <!-- Event Nodes -->
          <div
            v-for="(event, index) in chainEvents"
            :key="event.id"
            class="chain-node"
            :class="{ dragging: draggedEventId === event.id }"
            :style="{
              left: (nodePositions[event.id]?.x || 100) + 'px',
              top: (nodePositions[event.id]?.y || 100) + 'px',
              '--severity-color': severityColors[event.severity],
              '--chain-color': selectedChain.color,
            }"
            @mousedown="handleDragStart($event, event.id)"
          >
            <div class="node-stage-badge" :style="{ backgroundColor: selectedChain.color }">
              {{ index + 1 }}
            </div>
            <div class="node-header">
              <span class="node-icon">{{ getThreatIcon(event.type) }}</span>
              <span class="node-name">{{ event.name }}</span>
            </div>
            <div class="node-body">
              <div class="node-meta">
                <span class="meta-item">
                  <span class="meta-label">Duration:</span> {{ event.duration }}m
                </span>
                <span class="meta-item">
                  <span class="meta-label">Success:</span> {{ event.successProbability || 80 }}%
                </span>
              </div>
              <div class="node-severity" :style="{ backgroundColor: severityColors[event.severity] + '30' }">
                {{ event.severity }}
              </div>
            </div>
            <button
              class="node-remove"
              @click.stop="emit('removeEventFromChain', event.id)"
              title="Remove from chain"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <!-- Empty Chain State -->
          <div v-if="chainEvents.length === 0" class="empty-chain">
            <p>Drag events from the sidebar to build your attack chain</p>
            <p class="hint">Or click on available events to add them</p>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.chain-builder {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
}

.builder-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  color: var(--color-primary);
}

.header-title h3 {
  margin: 0;
  font-size: 1.1rem;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.builder-content {
  display: grid;
  grid-template-columns: 260px 1fr;
  flex: 1;
  overflow: hidden;
}

/* Sidebar */
.chain-sidebar {
  background: var(--bg-input);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.sidebar-section {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.sidebar-section h4 {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.chain-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.chain-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-card);
  border: 2px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chain-item:hover {
  border-color: var(--chain-color);
}

.chain-item.selected {
  border-color: var(--chain-color);
  background: linear-gradient(135deg, var(--bg-card), color-mix(in srgb, var(--chain-color) 10%, var(--bg-card)));
}

.chain-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chain-info {
  flex: 1;
  min-width: 0;
}

.chain-name {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

.chain-meta {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.chain-delete {
  width: 20px;
  height: 20px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  opacity: 0;
  transition: all var(--transition-fast);
}

.chain-item:hover .chain-delete {
  opacity: 1;
}

.chain-delete:hover {
  background: var(--color-error);
  color: white;
}

.empty-chains {
  text-align: center;
  padding: var(--spacing-md);
  color: var(--text-muted);
  font-size: 0.85rem;
}

.empty-chains p {
  margin-bottom: var(--spacing-sm);
}

/* Available Events */
.available-events {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 300px;
  overflow-y: auto;
}

.available-event {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.available-event:hover {
  border-color: var(--color-primary);
}

.event-icon {
  font-size: 1rem;
}

.event-info {
  flex: 1;
  min-width: 0;
}

.event-name {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-type {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: capitalize;
}

.add-btn {
  width: 20px;
  height: 20px;
  background: var(--color-primary);
  border: none;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.available-event:hover .add-btn {
  opacity: 1;
}

.no-events {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-align: center;
  padding: var(--spacing-sm);
}

/* Canvas Area */
.chain-canvas-area {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.no-chain-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  text-align: center;
  color: var(--text-secondary);
  max-width: 400px;
}

.empty-state h3 {
  margin-top: var(--spacing-md);
  color: var(--text-primary);
}

.empty-state p {
  margin-top: var(--spacing-sm);
  font-size: 0.9rem;
}

.chain-canvas {
  flex: 1;
  position: relative;
  overflow: auto;
  background:
    radial-gradient(circle at 1px 1px, var(--border-color) 1px, transparent 0);
  background-size: 20px 20px;
  min-height: 400px;
}

/* Chain Info Bar */
.chain-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 20;
}

.chain-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.chain-color-indicator {
  width: 16px;
  height: 16px;
  border-radius: var(--radius-sm);
}

.chain-name-edit {
  background: transparent;
  border: none;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.chain-name-edit:focus {
  outline: none;
  background: var(--bg-input);
}

.chain-stats {
  display: flex;
  gap: var(--spacing-lg);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.stat-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.low { color: #dc2626; }
.stat-value.medium { color: #f97316; }
.stat-value.high { color: #22c55e; }

/* SVG Connections */
.connections-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 5;
}

.connection-path {
  animation: dash 0.5s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -12;
  }
}

/* Chain Nodes */
.chain-node {
  position: absolute;
  width: 160px;
  background: var(--bg-card);
  border: 2px solid var(--severity-color);
  border-radius: var(--radius-md);
  cursor: grab;
  transition: box-shadow var(--transition-fast);
  z-index: 10;
  user-select: none;
}

.chain-node:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.chain-node.dragging {
  cursor: grabbing;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  z-index: 100;
  opacity: 0.95;
}

.node-stage-badge {
  position: absolute;
  top: -10px;
  left: -10px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 0.75rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}

.node-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.node-icon {
  font-size: 1rem;
}

.node-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-body {
  padding: var(--spacing-sm);
}

.node-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: var(--spacing-xs);
}

.meta-item {
  font-size: 0.65rem;
  color: var(--text-secondary);
}

.meta-label {
  color: var(--text-muted);
}

.node-severity {
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--severity-color);
}

.node-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background: var(--color-error);
  border: none;
  color: white;
  border-radius: 50%;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.chain-node:hover .node-remove {
  display: flex;
}

/* Empty Chain */
.empty-chain {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-secondary);
}

.empty-chain p {
  margin: 0;
}

.empty-chain .hint {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: var(--spacing-sm);
}

/* Button styles */
.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.75rem;
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-primary {
  background: var(--color-primary);
  border: none;
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}
</style>
