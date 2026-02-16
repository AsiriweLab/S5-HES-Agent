<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ScenarioBrowser from '@/components/ScenarioBrowser.vue'
import AttackChainBuilder from '@/components/AttackChainBuilder.vue'
import type { ThreatScenario, HomeScenario } from '@/services/PreloadedScenarioManager'
import { agentService, type ThreatGenerationRequest, type GeneratedThreatEvent } from '@/services/AgentService'

// Types
interface ThreatEvent {
  id: string
  type: ThreatType
  name: string
  startTime: number // minutes from simulation start
  duration: number // minutes
  severity: 'low' | 'medium' | 'high' | 'critical'
  severityValue: number // 1-100 for slider
  difficulty: number // 1-100 (how hard to execute)
  targetDevices: string[]
  description: string
  attackVector: string
  indicators: string[]
  // Multi-stage attack chain properties
  stageNumber?: number // Stage in attack chain (1, 2, 3...)
  dependsOn?: string[] // IDs of events that must complete before this one
  successProbability?: number // 0-100, likelihood of success
  isChainStart?: boolean // Is this the first event in a chain
}

// Attack Chain type for grouping related events
interface AttackChain {
  id: string
  name: string
  description: string
  color: string
  eventIds: string[] // Ordered list of event IDs in the chain
}

type ThreatType =
  // Original threats
  | 'man_in_the_middle'
  | 'denial_of_service'
  | 'replay_attack'
  | 'firmware_exploit'
  | 'credential_theft'
  | 'data_exfiltration'
  | 'device_hijack'
  | 'botnet_recruit'
  | 'ransomware'
  | 'side_channel'
  // New threats (Task #21)
  | 'energy_theft'
  | 'device_tampering'
  | 'unauthorized_access'
  | 'surveillance'
  | 'sensor_interception'
  | 'firmware_modification'
  | 'jamming'
  | 'resource_exhaustion'
  | 'safety_system_bypass'
  | 'hvac_manipulation'
  | 'meter_tampering'
  | 'usage_falsification'
  | 'location_tracking'
  | 'behavior_profiling'
  | 'dns_spoofing'
  | 'arp_poisoning'

interface ThreatTemplate {
  type: ThreatType
  name: string
  description: string
  icon: string
  color: string
  defaultDuration: number
  defaultSeverity: 'low' | 'medium' | 'high' | 'critical'
  defaultSeverityValue: number
  defaultDifficulty: number // 1-100 (how hard to execute)
  mitreTechniques: string[]
}

// State
const events = ref<ThreatEvent[]>([])
const selectedEvent = ref<ThreatEvent | null>(null)
const timelineZoom = ref(1) // 1 = 1 hour visible, 2 = 2 hours, etc.
const simulationDuration = ref(480) // 8 hours in minutes
const currentTime = ref(0)
// isPlaying will be used for timeline playback feature
// const isPlaying = ref(false)

// Scenario Browser state
const showScenarioBrowser = ref(false)

// AI Agent Generation state
const showAIGenerator = ref(false)
const isGenerating = ref(false)
const generationProgress = ref('')
const generationError = ref<string | null>(null) // Track generation errors
const isLLMAvailable = ref<boolean | null>(null) // Track LLM availability
const isCheckingLLM = ref(false) // Track LLM check status
// RESEARCH INTEGRITY: Track whether unverified (synthetic) data is allowed
const allowUnverifiedMode = ref(false)
const lastGenerationVerified = ref<boolean | null>(null) // Track if last generation was verified

// Threat Preview state
const showPreview = ref(false)
const previewProgress = ref(0)
const previewPhase = ref<'idle' | 'initializing' | 'executing' | 'propagating' | 'complete'>('idle')
const previewLogs = ref<Array<{ time: string; type: 'info' | 'warning' | 'danger' | 'success'; message: string }>>([])
let previewInterval: ReturnType<typeof setInterval> | null = null

// AI Scenario Analysis state
const showAnalysisPanel = ref(false)
const isAnalyzing = ref(false)
const analysisResult = ref<{
  summary: string
  riskScore: number
  vulnerabilities: string[]
  attackPaths: string[]
  recommendations: Array<{
    id: string
    title: string
    description: string
    priority: 'low' | 'medium' | 'high' | 'critical'
    mitigates: string[]
    implementationSteps: string[]
    estimatedEffort: string
  }>
  mitreCoverage: string[]
} | null>(null)

const aiConfig = ref<ThreatGenerationRequest>({
  homeType: 'smart_home',
  deviceTypes: ['smart_thermostat', 'smart_camera', 'smart_lock', 'smart_speaker'],
  securityLevel: 'medium',
  attackDifficulty: 'intermediate',
  targetCategory: undefined,
  duration: 480,
  numEvents: 5,
  allowUnverified: false, // Default to strict mode
})

// Multi-stage attack chain state
const attackChains = ref<AttackChain[]>([])
const selectedChain = ref<AttackChain | null>(null)
const isChainMode = ref(false) // Toggle for chain creation mode
const chainLinkSource = ref<ThreatEvent | null>(null) // Event being linked from
const showChainBuilder = ref(false) // Visual chain builder modal

// Chain color palette
const chainColors = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6',
  '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899',
]

// Drag state for timeline events
const timelineCanvasRef = ref<HTMLElement | null>(null)
const isDraggingEvent = ref(false)
const draggedEvent = ref<ThreatEvent | null>(null)
const dragStartX = ref(0)
const dragStartTime = ref(0)

// Resize state for event duration
const isResizingEvent = ref(false)
const resizeEvent = ref<ThreatEvent | null>(null)
const resizeStartX = ref(0)
const resizeStartDuration = ref(0)

// Threat types
const threatTemplates: ThreatTemplate[] = [
  {
    type: 'man_in_the_middle',
    name: 'Man-in-the-Middle',
    description: 'Intercepts communication between devices',
    icon: '🕵️',
    color: '#ef4444',
    defaultDuration: 30,
    defaultSeverity: 'high',
    defaultSeverityValue: 75,
    defaultDifficulty: 60,
    mitreTechniques: ['T1557', 'T1040'],
  },
  {
    type: 'denial_of_service',
    name: 'Denial of Service',
    description: 'Overwhelms device with traffic',
    icon: '🚫',
    color: '#f97316',
    defaultDuration: 15,
    defaultSeverity: 'medium',
    defaultSeverityValue: 50,
    defaultDifficulty: 25,
    mitreTechniques: ['T1498', 'T1499'],
  },
  {
    type: 'replay_attack',
    name: 'Replay Attack',
    description: 'Captures and retransmits valid data',
    icon: '🔄',
    color: '#eab308',
    defaultDuration: 10,
    defaultSeverity: 'medium',
    defaultSeverityValue: 45,
    defaultDifficulty: 35,
    mitreTechniques: ['T1550'],
  },
  {
    type: 'firmware_exploit',
    name: 'Firmware Exploit',
    description: 'Exploits vulnerabilities in device firmware',
    icon: '🔧',
    color: '#8b5cf6',
    defaultDuration: 45,
    defaultSeverity: 'critical',
    defaultSeverityValue: 95,
    defaultDifficulty: 85,
    mitreTechniques: ['T1542', 'T1195'],
  },
  {
    type: 'credential_theft',
    name: 'Credential Theft',
    description: 'Steals authentication credentials',
    icon: '🔑',
    color: '#ec4899',
    defaultDuration: 20,
    defaultSeverity: 'high',
    defaultSeverityValue: 70,
    defaultDifficulty: 45,
    mitreTechniques: ['T1003', 'T1555'],
  },
  {
    type: 'data_exfiltration',
    name: 'Data Exfiltration',
    description: 'Extracts sensitive data from devices',
    icon: '📤',
    color: '#06b6d4',
    defaultDuration: 60,
    defaultSeverity: 'high',
    defaultSeverityValue: 80,
    defaultDifficulty: 55,
    mitreTechniques: ['T1041', 'T1048'],
  },
  {
    type: 'device_hijack',
    name: 'Device Hijack',
    description: 'Takes control of IoT device',
    icon: '🎮',
    color: '#14b8a6',
    defaultDuration: 25,
    defaultSeverity: 'critical',
    defaultSeverityValue: 90,
    defaultDifficulty: 70,
    mitreTechniques: ['T1219', 'T1021'],
  },
  {
    type: 'botnet_recruit',
    name: 'Botnet Recruitment',
    description: 'Enrolls device into a botnet',
    icon: '🤖',
    color: '#6366f1',
    defaultDuration: 35,
    defaultSeverity: 'critical',
    defaultSeverityValue: 85,
    defaultDifficulty: 50,
    mitreTechniques: ['T1583', 'T1584'],
  },
  {
    type: 'ransomware',
    name: 'Ransomware',
    description: 'Encrypts data and demands payment',
    icon: '💰',
    color: '#dc2626',
    defaultDuration: 40,
    defaultSeverity: 'critical',
    defaultSeverityValue: 100,
    defaultDifficulty: 65,
    mitreTechniques: ['T1486', 'T1490'],
  },
  {
    type: 'side_channel',
    name: 'Side-Channel Attack',
    description: 'Extracts info through indirect means',
    icon: '📊',
    color: '#84cc16',
    defaultDuration: 90,
    defaultSeverity: 'low',
    defaultSeverityValue: 25,
    defaultDifficulty: 90,
    mitreTechniques: ['T1592'],
  },
  // Additional threat types to match backend (22 total)
  {
    type: 'energy_theft',
    name: 'Energy Theft',
    description: 'Manipulates smart meter readings',
    icon: '⚡',
    color: '#fbbf24',
    defaultDuration: 120,
    defaultSeverity: 'medium',
    defaultSeverityValue: 55,
    defaultDifficulty: 45,
    mitreTechniques: ['T1565'],
  },
  {
    type: 'device_tampering',
    name: 'Device Tampering',
    description: 'Physical manipulation of device behavior',
    icon: '🔨',
    color: '#a855f7',
    defaultDuration: 30,
    defaultSeverity: 'high',
    defaultSeverityValue: 70,
    defaultDifficulty: 55,
    mitreTechniques: ['T1200'],
  },
  {
    type: 'unauthorized_access',
    name: 'Unauthorized Access',
    description: 'Gains unauthorized control of devices',
    icon: '🚪',
    color: '#f43f5e',
    defaultDuration: 25,
    defaultSeverity: 'high',
    defaultSeverityValue: 75,
    defaultDifficulty: 40,
    mitreTechniques: ['T1078', 'T1110'],
  },
  {
    type: 'surveillance',
    name: 'Surveillance',
    description: 'Monitors home through compromised devices',
    icon: '👁️',
    color: '#0ea5e9',
    defaultDuration: 180,
    defaultSeverity: 'high',
    defaultSeverityValue: 80,
    defaultDifficulty: 50,
    mitreTechniques: ['T1125', 'T1123'],
  },
  {
    type: 'sensor_interception',
    name: 'Sensor Interception',
    description: 'Intercepts sensor data streams',
    icon: '📡',
    color: '#10b981',
    defaultDuration: 45,
    defaultSeverity: 'medium',
    defaultSeverityValue: 55,
    defaultDifficulty: 40,
    mitreTechniques: ['T1040'],
  },
  {
    type: 'hvac_manipulation',
    name: 'HVAC Manipulation',
    description: 'Manipulates heating/cooling systems',
    icon: '🌡️',
    color: '#f59e0b',
    defaultDuration: 60,
    defaultSeverity: 'medium',
    defaultSeverityValue: 50,
    defaultDifficulty: 35,
    mitreTechniques: ['T1565'],
  },
  {
    type: 'safety_system_bypass',
    name: 'Safety System Bypass',
    description: 'Bypasses smoke/CO/leak detectors',
    icon: '🚨',
    color: '#dc2626',
    defaultDuration: 15,
    defaultSeverity: 'critical',
    defaultSeverityValue: 95,
    defaultDifficulty: 60,
    mitreTechniques: ['T1562'],
  },
  {
    type: 'dns_spoofing',
    name: 'DNS Spoofing',
    description: 'Poisons DNS to redirect device traffic',
    icon: '🌐',
    color: '#7c3aed',
    defaultDuration: 30,
    defaultSeverity: 'high',
    defaultSeverityValue: 70,
    defaultDifficulty: 50,
    mitreTechniques: ['T1557.002'],
  },
  {
    type: 'arp_poisoning',
    name: 'ARP Poisoning',
    description: 'Manipulates ARP tables for traffic interception',
    icon: '🔗',
    color: '#be185d',
    defaultDuration: 25,
    defaultSeverity: 'high',
    defaultSeverityValue: 65,
    defaultDifficulty: 45,
    mitreTechniques: ['T1557.002'],
  },
  {
    type: 'meter_tampering',
    name: 'Meter Tampering',
    description: 'Physical tampering with smart meters',
    icon: '🔌',
    color: '#ea580c',
    defaultDuration: 90,
    defaultSeverity: 'high',
    defaultSeverityValue: 70,
    defaultDifficulty: 70,
    mitreTechniques: ['T1200', 'T1565'],
  },
  {
    type: 'usage_falsification',
    name: 'Usage Falsification',
    description: 'Falsifies energy usage reports',
    icon: '📉',
    color: '#ca8a04',
    defaultDuration: 60,
    defaultSeverity: 'medium',
    defaultSeverityValue: 55,
    defaultDifficulty: 50,
    mitreTechniques: ['T1565'],
  },
  {
    type: 'jamming',
    name: 'Wireless Jamming',
    description: 'Jams wireless signals (WiFi, Zigbee, Z-Wave)',
    icon: '📶',
    color: '#64748b',
    defaultDuration: 30,
    defaultSeverity: 'high',
    defaultSeverityValue: 65,
    defaultDifficulty: 30,
    mitreTechniques: ['T1464'],
  },
  {
    type: 'resource_exhaustion',
    name: 'Resource Exhaustion',
    description: 'Exhausts device CPU/memory/battery',
    icon: '🔋',
    color: '#991b1b',
    defaultDuration: 45,
    defaultSeverity: 'medium',
    defaultSeverityValue: 60,
    defaultDifficulty: 35,
    mitreTechniques: ['T1499'],
  },
  {
    type: 'location_tracking',
    name: 'Location Tracking',
    description: 'Tracks occupant movement through sensors',
    icon: '📍',
    color: '#059669',
    defaultDuration: 240,
    defaultSeverity: 'medium',
    defaultSeverityValue: 50,
    defaultDifficulty: 40,
    mitreTechniques: ['T1430'],
  },
  {
    type: 'behavior_profiling',
    name: 'Behavior Profiling',
    description: 'Builds behavioral profiles of occupants',
    icon: '🧠',
    color: '#4f46e5',
    defaultDuration: 480,
    defaultSeverity: 'medium',
    defaultSeverityValue: 55,
    defaultDifficulty: 45,
    mitreTechniques: ['T1592'],
  },
]

// Computed
// timelineWidth will be used for dynamic timeline scaling
// const timelineWidth = computed(() => simulationDuration.value * timelineZoom.value)

const sortedEvents = computed(() =>
  [...events.value].sort((a, b) => a.startTime - b.startTime)
)

const totalThreats = computed(() => events.value.length)

const severityCounts = computed(() => ({
  critical: events.value.filter(e => e.severity === 'critical').length,
  high: events.value.filter(e => e.severity === 'high').length,
  medium: events.value.filter(e => e.severity === 'medium').length,
  low: events.value.filter(e => e.severity === 'low').length,
}))

// Methods
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function getThreatTemplate(type: ThreatType): ThreatTemplate | undefined {
  return threatTemplates.find(t => t.type === type)
}

function addThreatEvent(type: ThreatType) {
  const template = getThreatTemplate(type)
  if (!template) return

  // Find a suitable start time (after existing events or at current position)
  const lastEvent = events.value[events.value.length - 1]
  const startTime = lastEvent
    ? Math.min(lastEvent.startTime + lastEvent.duration + 10, simulationDuration.value - template.defaultDuration)
    : Math.min(currentTime.value, simulationDuration.value - template.defaultDuration)

  const newEvent: ThreatEvent = {
    id: generateId(),
    type,
    name: `${template.name} ${events.value.filter(e => e.type === type).length + 1}`,
    startTime: Math.max(0, startTime),
    duration: template.defaultDuration,
    severity: template.defaultSeverity,
    severityValue: template.defaultSeverityValue,
    difficulty: template.defaultDifficulty,
    targetDevices: [],
    description: template.description,
    attackVector: template.mitreTechniques[0] || '',
    indicators: [],
  }

  events.value.push(newEvent)
  selectedEvent.value = newEvent
}

function selectEvent(event: ThreatEvent) {
  selectedEvent.value = event
}

function deleteEvent(eventId: string) {
  const index = events.value.findIndex(e => e.id === eventId)
  if (index !== -1) {
    events.value.splice(index, 1)
    if (selectedEvent.value?.id === eventId) {
      selectedEvent.value = null
    }
  }
}

function formatTime(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`
}

function getEventStyle(event: ThreatEvent) {
  const template = getThreatTemplate(event.type)
  const left = (event.startTime / simulationDuration.value) * 100
  const width = (event.duration / simulationDuration.value) * 100

  return {
    left: `${left}%`,
    width: `${width}%`,
    backgroundColor: `${template?.color || '#6b7280'}30`,
    borderColor: template?.color || '#6b7280',
  }
}

// Get SVG path for curved chain arrows (like Chain Builder)
function getConnectionPath(conn: { from: ThreatEvent; to: ThreatEvent; color: string }): string {
  // Find indices in sorted events to determine vertical positions
  const fromIndex = sortedEvents.value.findIndex(e => e.id === conn.from.id)
  const toIndex = sortedEvents.value.findIndex(e => e.id === conn.to.id)

  // Get actual canvas dimensions
  const canvasWidth = timelineCanvasRef.value?.clientWidth || 800

  // Calculate x positions in pixels (end of 'from' event to start of 'to' event)
  const x1 = ((conn.from.startTime + conn.from.duration) / simulationDuration.value) * canvasWidth
  const x2 = (conn.to.startTime / simulationDuration.value) * canvasWidth

  // Calculate y positions: 20px top offset + (row * 70px row height) + 30px (half of 60px event height)
  const y1 = 20 + (fromIndex % 4) * 70 + 30
  const y2 = 20 + (toIndex % 4) * 70 + 30

  // Create cubic bezier curve like Chain Builder
  const midX = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
}

function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    critical: '#dc2626',
    high: '#f97316',
    medium: '#eab308',
    low: '#22c55e',
  }
  return colors[severity] || '#6b7280'
}

function getSeverityFromValue(value: number): 'low' | 'medium' | 'high' | 'critical' {
  if (value >= 76) return 'critical'
  if (value >= 51) return 'high'
  if (value >= 26) return 'medium'
  return 'low'
}

function getDifficultyLabel(value: number): string {
  if (value >= 76) return 'Expert'
  if (value >= 51) return 'Advanced'
  if (value >= 26) return 'Intermediate'
  return 'Beginner'
}

function getDifficultyColor(value: number): string {
  if (value >= 76) return '#dc2626'
  if (value >= 51) return '#f97316'
  if (value >= 26) return '#eab308'
  return '#22c55e'
}

function updateSeverityFromSlider(event: ThreatEvent) {
  event.severity = getSeverityFromValue(event.severityValue)
}

// Threat Preview Functions
function startPreview(event: ThreatEvent) {
  if (previewInterval) {
    clearInterval(previewInterval)
  }

  showPreview.value = true
  previewProgress.value = 0
  previewPhase.value = 'initializing'
  previewLogs.value = []

  const template = getThreatTemplate(event.type)
  const targetCount = event.targetDevices.length || 1

  // Add initial log
  addPreviewLog('info', `Initializing ${event.name}...`)

  // Simulate the attack execution over time
  let step = 0
  const totalSteps = 20
  const stepDuration = 200 // ms per step

  previewInterval = setInterval(() => {
    step++
    previewProgress.value = Math.min((step / totalSteps) * 100, 100)

    // Update phase based on progress
    if (step === 2) {
      previewPhase.value = 'executing'
      addPreviewLog('warning', `Attack vector: ${event.attackVector || template?.mitreTechniques[0] || 'Unknown'}`)
    } else if (step === 5) {
      addPreviewLog('info', `Targeting ${targetCount} device(s)...`)
    } else if (step === 8) {
      addPreviewLog('danger', `Executing ${template?.name || event.type} attack`)
    } else if (step === 12) {
      previewPhase.value = 'propagating'
      addPreviewLog('warning', `Severity: ${event.severity.toUpperCase()} (${event.severityValue}/100)`)
    } else if (step === 15) {
      addPreviewLog('info', `Attack difficulty: ${getDifficultyLabel(event.difficulty)}`)
    } else if (step === 18) {
      if (event.indicators && event.indicators.length > 0) {
        addPreviewLog('info', `IoCs detected: ${event.indicators.length} indicators`)
      }
    } else if (step >= totalSteps) {
      previewPhase.value = 'complete'
      addPreviewLog('success', `Preview complete - Duration: ${event.duration} minutes`)
      if (previewInterval) {
        clearInterval(previewInterval)
        previewInterval = null
      }
    }
  }, stepDuration)
}

function stopPreview() {
  if (previewInterval) {
    clearInterval(previewInterval)
    previewInterval = null
  }
  showPreview.value = false
  previewProgress.value = 0
  previewPhase.value = 'idle'
  previewLogs.value = []
}

function addPreviewLog(type: 'info' | 'warning' | 'danger' | 'success', message: string) {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  previewLogs.value.push({ time, type, message })
}

// Timeline drag handlers
function handleEventDragStart(mouseEvent: MouseEvent, event: ThreatEvent) {
  // Don't start drag if clicking on resize handle or delete button
  if ((mouseEvent.target as HTMLElement).closest('.event-resize-handle')) return
  if ((mouseEvent.target as HTMLElement).closest('.event-delete')) return

  mouseEvent.preventDefault()
  mouseEvent.stopPropagation()

  isDraggingEvent.value = true
  draggedEvent.value = event
  dragStartX.value = mouseEvent.clientX
  dragStartTime.value = event.startTime
  selectedEvent.value = event

  document.addEventListener('mousemove', handleEventDragMove)
  document.addEventListener('mouseup', handleEventDragEnd)
}

function handleEventDragMove(mouseEvent: MouseEvent) {
  if (!isDraggingEvent.value || !draggedEvent.value || !timelineCanvasRef.value) return

  const canvas = timelineCanvasRef.value
  const canvasRect = canvas.getBoundingClientRect()
  const canvasWidth = canvasRect.width

  // Calculate the delta in pixels
  const deltaX = mouseEvent.clientX - dragStartX.value

  // Convert pixel delta to time delta
  const timePerPixel = simulationDuration.value / canvasWidth
  const deltaTime = deltaX * timePerPixel

  // Calculate new start time
  let newStartTime = dragStartTime.value + deltaTime

  // Clamp to valid range
  newStartTime = Math.max(0, Math.min(simulationDuration.value - draggedEvent.value.duration, newStartTime))

  // Snap to 5-minute increments
  newStartTime = Math.round(newStartTime / 5) * 5

  draggedEvent.value.startTime = newStartTime
}

function handleEventDragEnd() {
  isDraggingEvent.value = false
  draggedEvent.value = null

  document.removeEventListener('mousemove', handleEventDragMove)
  document.removeEventListener('mouseup', handleEventDragEnd)
}

// Timeline resize handlers
function handleEventResizeStart(mouseEvent: MouseEvent, event: ThreatEvent) {
  mouseEvent.preventDefault()
  mouseEvent.stopPropagation()

  isResizingEvent.value = true
  resizeEvent.value = event
  resizeStartX.value = mouseEvent.clientX
  resizeStartDuration.value = event.duration
  selectedEvent.value = event

  document.addEventListener('mousemove', handleEventResizeMove)
  document.addEventListener('mouseup', handleEventResizeEnd)
}

function handleEventResizeMove(mouseEvent: MouseEvent) {
  if (!isResizingEvent.value || !resizeEvent.value || !timelineCanvasRef.value) return

  const canvas = timelineCanvasRef.value
  const canvasRect = canvas.getBoundingClientRect()
  const canvasWidth = canvasRect.width

  // Calculate the delta in pixels
  const deltaX = mouseEvent.clientX - resizeStartX.value

  // Convert pixel delta to time delta
  const timePerPixel = simulationDuration.value / canvasWidth
  const deltaTime = deltaX * timePerPixel

  // Calculate new duration
  let newDuration = resizeStartDuration.value + deltaTime

  // Clamp to valid range (min 5 minutes, max to end of simulation)
  const maxDuration = simulationDuration.value - resizeEvent.value.startTime
  newDuration = Math.max(5, Math.min(maxDuration, newDuration))

  // Snap to 5-minute increments
  newDuration = Math.round(newDuration / 5) * 5

  resizeEvent.value.duration = newDuration
}

function handleEventResizeEnd() {
  isResizingEvent.value = false
  resizeEvent.value = null

  document.removeEventListener('mousemove', handleEventResizeMove)
  document.removeEventListener('mouseup', handleEventResizeEnd)
}

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('mousemove', handleEventDragMove)
  document.removeEventListener('mouseup', handleEventDragEnd)
  document.removeEventListener('mousemove', handleEventResizeMove)
  document.removeEventListener('mouseup', handleEventResizeEnd)
})

// Load threat created from chat action (via sessionStorage)
function loadChatCreatedThreat(): boolean {
  const savedData = sessionStorage.getItem('chatCreatedThreat')
  if (!savedData) return false

  try {
    const createdThreat = JSON.parse(savedData)

    // Map backend threat_type to frontend ThreatType
    const threatTypeMap: Record<string, ThreatType> = {
      'data_exfiltration': 'data_exfiltration',
      'credential_theft': 'credential_theft',
      'device_tampering': 'device_hijack',
      'botnet_recruitment': 'botnet_recruit',
      'ransomware': 'ransomware',
      'denial_of_service': 'denial_of_service',
      'unauthorized_access': 'device_hijack',
      'surveillance': 'side_channel',
      'man_in_the_middle': 'man_in_the_middle',
      'energy_theft': 'data_exfiltration',
    }

    const threatType = threatTypeMap[createdThreat.threat_type] || 'data_exfiltration'
    const template = getThreatTemplate(threatType)

    // Map severity string to severity values
    const severityMap: Record<string, { severity: 'low' | 'medium' | 'high' | 'critical', value: number }> = {
      'low': { severity: 'low', value: 20 },
      'medium': { severity: 'medium', value: 50 },
      'high': { severity: 'high', value: 75 },
      'critical': { severity: 'critical', value: 95 },
    }
    const severityInfo = severityMap[createdThreat.severity] || severityMap['medium']

    // Create a ThreatEvent from the chat-created threat
    const newEvent: ThreatEvent = {
      id: createdThreat.id || generateId(),
      type: threatType,
      name: createdThreat.name || template?.name || 'Chat-Created Threat',
      startTime: 0, // Start at beginning
      duration: template?.defaultDuration || 30,
      severity: severityInfo.severity,
      severityValue: severityInfo.value,
      difficulty: template?.defaultDifficulty || 50,
      targetDevices: createdThreat.target_device_types || [],
      description: createdThreat.description || template?.description || '',
      attackVector: createdThreat.mitre_techniques?.[0] || template?.mitreTechniques?.[0] || '',
      indicators: createdThreat.indicators?.map((i: { name: string }) => i.name) || [],
    }

    // Add the event
    events.value.push(newEvent)
    selectedEvent.value = newEvent

    // Clear the sessionStorage after loading
    sessionStorage.removeItem('chatCreatedThreat')

    console.log(`[ThreatBuilder] Loaded chat-created threat: ${newEvent.name}`)
    return true
  } catch (err) {
    console.error('[ThreatBuilder] Failed to load chat-created threat:', err)
    sessionStorage.removeItem('chatCreatedThreat')
    return false
  }
}

// On mount, check for chat-created threat data
onMounted(() => {
  loadChatCreatedThreat()
})

function clearAll() {
  if (confirm('Are you sure you want to clear all threat events?')) {
    events.value = []
    selectedEvent.value = null
  }
}

function saveScenario() {
  const scenario = {
    events: events.value,
    simulationDuration: simulationDuration.value,
    createdAt: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(scenario, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `threat-scenario-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// File input ref for loading scenarios
const scenarioFileInputRef = ref<HTMLInputElement | null>(null)

function triggerScenarioLoad() {
  scenarioFileInputRef.value?.click()
}

function handleScenarioLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const scenario = JSON.parse(content)

      // Validate the scenario structure
      if (!scenario.events || !Array.isArray(scenario.events)) {
        alert('Invalid scenario file: missing events array')
        return
      }

      // Clear existing events
      events.value = []
      selectedEvent.value = null

      // Load simulation duration if present
      if (scenario.simulationDuration && typeof scenario.simulationDuration === 'number') {
        simulationDuration.value = scenario.simulationDuration
      }

      // Load events with validation
      scenario.events.forEach((evt: ThreatEvent) => {
        if (evt.id && evt.type && evt.name) {
          // Ensure all required fields have defaults
          const validEvent: ThreatEvent = {
            id: evt.id,
            type: evt.type,
            name: evt.name,
            startTime: evt.startTime ?? 0,
            duration: evt.duration ?? 30,
            severity: evt.severity ?? 'medium',
            severityValue: evt.severityValue ?? 50,
            difficulty: evt.difficulty ?? 50,
            targetDevices: evt.targetDevices ?? [],
            description: evt.description ?? '',
            attackVector: evt.attackVector ?? '',
            indicators: evt.indicators ?? [],
          }
          events.value.push(validEvent)
        }
      })

      // Select first event if available
      if (events.value.length > 0) {
        selectedEvent.value = events.value[0]
      }

      alert(`Loaded ${events.value.length} threat events`)
    } catch (err) {
      console.error('Failed to parse scenario file:', err)
      alert('Failed to load scenario: Invalid JSON format')
    }
  }
  reader.readAsText(file)

  // Reset input to allow loading the same file again
  input.value = ''
}

function zoomIn() {
  timelineZoom.value = Math.min(timelineZoom.value * 1.5, 5)
}

function zoomOut() {
  timelineZoom.value = Math.max(timelineZoom.value / 1.5, 0.5)
}

// ============== MULTI-STAGE ATTACK CHAIN FUNCTIONS ==============

function toggleChainMode() {
  isChainMode.value = !isChainMode.value
  if (!isChainMode.value) {
    chainLinkSource.value = null
  }
}

function createNewChain() {
  const newChain: AttackChain = {
    id: generateId(),
    name: `Attack Chain ${attackChains.value.length + 1}`,
    description: 'Multi-stage attack scenario',
    color: chainColors[attackChains.value.length % chainColors.length],
    eventIds: [],
  }
  attackChains.value.push(newChain)
  selectedChain.value = newChain
  isChainMode.value = true
}

function deleteChain(chainId: string) {
  const chain = attackChains.value.find(c => c.id === chainId)
  if (!chain) return

  // Remove chain references from events
  chain.eventIds.forEach(eventId => {
    const event = events.value.find(e => e.id === eventId)
    if (event) {
      event.stageNumber = undefined
      event.dependsOn = undefined
      event.isChainStart = undefined
    }
  })

  // Remove the chain
  const index = attackChains.value.findIndex(c => c.id === chainId)
  if (index !== -1) {
    attackChains.value.splice(index, 1)
  }

  if (selectedChain.value?.id === chainId) {
    selectedChain.value = null
  }
}

function addEventToChain(event: ThreatEvent, chain?: AttackChain) {
  const targetChain = chain || selectedChain.value
  if (!targetChain) return

  // Don't add if already in this chain
  if (targetChain.eventIds.includes(event.id)) return

  // Remove from any other chain first
  attackChains.value.forEach(c => {
    const idx = c.eventIds.indexOf(event.id)
    if (idx !== -1) {
      c.eventIds.splice(idx, 1)
    }
  })

  // Add to target chain
  targetChain.eventIds.push(event.id)

  // Update event properties
  event.stageNumber = targetChain.eventIds.length
  event.isChainStart = targetChain.eventIds.length === 1

  // Set dependency on previous event in chain
  if (targetChain.eventIds.length > 1) {
    const prevEventId = targetChain.eventIds[targetChain.eventIds.length - 2]
    event.dependsOn = [prevEventId]
  } else {
    event.dependsOn = []
  }

  // Default success probability if not set
  if (event.successProbability === undefined) {
    event.successProbability = 80
  }
}

function removeEventFromChain(eventId: string) {
  attackChains.value.forEach(chain => {
    const idx = chain.eventIds.indexOf(eventId)
    if (idx !== -1) {
      chain.eventIds.splice(idx, 1)

      // Update stage numbers for remaining events
      chain.eventIds.forEach((id, i) => {
        const evt = events.value.find(e => e.id === id)
        if (evt) {
          evt.stageNumber = i + 1
          evt.isChainStart = i === 0
          if (i > 0) {
            evt.dependsOn = [chain.eventIds[i - 1]]
          } else {
            evt.dependsOn = []
          }
        }
      })
    }
  })

  // Clear chain properties from event
  const event = events.value.find(e => e.id === eventId)
  if (event) {
    event.stageNumber = undefined
    event.dependsOn = undefined
    event.isChainStart = undefined
  }
}

function getEventChain(eventId: string): AttackChain | undefined {
  return attackChains.value.find(c => c.eventIds.includes(eventId))
}

function getChainColor(eventId: string): string | undefined {
  const chain = getEventChain(eventId)
  return chain?.color
}

function handleChainLinkClick(event: ThreatEvent) {
  if (!isChainMode.value) return

  if (!chainLinkSource.value) {
    // Start linking from this event
    chainLinkSource.value = event
  } else {
    // Complete the link
    if (chainLinkSource.value.id !== event.id) {
      // Ensure both events are in the same chain or create dependency
      const sourceChain = getEventChain(chainLinkSource.value.id)

      if (sourceChain) {
        // Add target event after source in chain
        if (!sourceChain.eventIds.includes(event.id)) {
          addEventToChain(event, sourceChain)
        }
        // Update dependency
        event.dependsOn = [...(event.dependsOn || []), chainLinkSource.value.id]
      } else if (selectedChain.value) {
        // Add both to selected chain
        addEventToChain(chainLinkSource.value, selectedChain.value)
        addEventToChain(event, selectedChain.value)
      }
    }
    chainLinkSource.value = null
  }
}

// Computed for chain visualization
const chainConnections = computed(() => {
  const connections: { from: ThreatEvent; to: ThreatEvent; color: string }[] = []

  attackChains.value.forEach(chain => {
    for (let i = 1; i < chain.eventIds.length; i++) {
      const fromEvent = events.value.find(e => e.id === chain.eventIds[i - 1])
      const toEvent = events.value.find(e => e.id === chain.eventIds[i])
      if (fromEvent && toEvent) {
        connections.push({ from: fromEvent, to: toEvent, color: chain.color })
      }
    }
  })

  return connections
})

// Load preloaded scenario from browser
function loadPreloadedScenario(scenario: ThreatScenario | HomeScenario) {
  // Check if it's a threat scenario
  if ('events' in scenario && 'category' in scenario) {
    const threatScenario = scenario as ThreatScenario

    // Clear existing events
    events.value = []
    selectedEvent.value = null

    // Load simulation duration
    if (threatScenario.simulationDuration) {
      simulationDuration.value = threatScenario.simulationDuration
    }

    // Load events
    threatScenario.events.forEach(evt => {
      const validEvent: ThreatEvent = {
        id: evt.id || generateId(),
        type: evt.type as ThreatType,
        name: evt.name,
        startTime: evt.startTime ?? 0,
        duration: evt.duration ?? 30,
        severity: evt.severity ?? 'medium',
        severityValue: evt.severityValue ?? 50,
        difficulty: evt.difficulty ?? 50,
        targetDevices: evt.targetDevices ?? [],
        description: evt.description ?? '',
        attackVector: evt.attackVector ?? '',
        indicators: evt.indicators ?? [],
      }
      events.value.push(validEvent)
    })

    // Select first event if available
    if (events.value.length > 0) {
      selectedEvent.value = events.value[0]
    }

    showScenarioBrowser.value = false
  }
}

// ============== AI AGENT GENERATION FUNCTIONS ==============

async function generateAIThreats() {
  if (isGenerating.value) return

  isGenerating.value = true
  generationProgress.value = 'Initializing AI agent...'
  generationError.value = null

  try {
    // Update config with current simulation duration and unverified mode setting
    aiConfig.value.duration = simulationDuration.value
    aiConfig.value.allowUnverified = allowUnverifiedMode.value

    generationProgress.value = 'Generating threat scenarios (this may take 30-60 seconds)...'

    const response = await agentService.generateThreats(aiConfig.value)

    if (response.success && response.events.length > 0) {
      generationProgress.value = 'Loading generated events...'

      // RESEARCH INTEGRITY: Track verification status
      lastGenerationVerified.value = response.verified

      // Convert and add generated events
      response.events.forEach((genEvent: GeneratedThreatEvent) => {
        const newEvent: ThreatEvent = {
          id: genEvent.id || generateId(),
          type: genEvent.type as ThreatType,
          name: genEvent.name,
          startTime: genEvent.startTime,
          duration: genEvent.duration,
          severity: genEvent.severity,
          severityValue: genEvent.severityValue,
          difficulty: genEvent.difficulty,
          targetDevices: genEvent.targetDevices,
          description: genEvent.description,
          attackVector: genEvent.attackVector,
          indicators: genEvent.indicators,
          stageNumber: genEvent.stageNumber,
          dependsOn: genEvent.dependsOn,
          successProbability: genEvent.successProbability,
        }
        events.value.push(newEvent)
      })

      // Select first generated event
      if (events.value.length > 0) {
        selectedEvent.value = events.value[events.value.length - response.events.length]
      }

      // Show appropriate message based on verification status
      if (response.verified) {
        generationProgress.value = `Successfully generated ${response.events.length} threat events!`
      } else {
        generationProgress.value = `Generated ${response.events.length} UNVERIFIED events (synthetic data)`
      }

      // Auto-close modal after success
      setTimeout(() => {
        showAIGenerator.value = false
        generationProgress.value = ''
        generationError.value = null
      }, 1500)
    } else {
      generationError.value = response.message || 'Failed to generate threats - no events returned'
      generationProgress.value = ''
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Generation failed'
    generationError.value = errorMsg
    generationProgress.value = ''
    // Refresh LLM status on error
    checkLLMStatus()
  } finally {
    isGenerating.value = false
  }
}

async function checkLLMStatus() {
  isCheckingLLM.value = true
  try {
    isLLMAvailable.value = await agentService.checkLLMHealth()
  } catch {
    isLLMAvailable.value = false
  } finally {
    isCheckingLLM.value = false
  }
}

function dismissError() {
  generationError.value = null
}

function retryGeneration() {
  generationError.value = null
  generateAIThreats()
}

function openAIGenerator() {
  showAIGenerator.value = true
  generationError.value = null
  generationProgress.value = ''
  // Check LLM status when opening the modal
  checkLLMStatus()
}

async function generateAIAttackChain() {
  if (isGenerating.value) return

  isGenerating.value = true
  generationProgress.value = 'Generating attack chain...'
  generationError.value = null

  try {
    const homeConfig = {
      devices: aiConfig.value.deviceTypes,
      rooms: ['living_room', 'bedroom', 'kitchen'], // Default rooms
    }

    // RESEARCH INTEGRITY: Pass allowUnverified setting
    const response = await agentService.generateAttackChain(
      homeConfig,
      'Compromise smart home and exfiltrate data',
      allowUnverifiedMode.value
    )

    if (response.success && response.events.length > 0) {
      generationProgress.value = 'Creating attack chain...'

      // RESEARCH INTEGRITY: Track verification status
      lastGenerationVerified.value = response.verified

      // Create a new chain for the generated events
      const chainName = response.verified
        ? 'AI Generated Attack Chain'
        : 'AI Generated Attack Chain (UNVERIFIED)'
      const newChain: AttackChain = {
        id: generateId(),
        name: chainName,
        description: response.attackChainDescription || 'Multi-stage attack scenario',
        color: chainColors[attackChains.value.length % chainColors.length],
        eventIds: [],
      }

      // Add events and link them to the chain
      response.events.forEach((genEvent: GeneratedThreatEvent, index: number) => {
        const newEvent: ThreatEvent = {
          id: genEvent.id || generateId(),
          type: genEvent.type as ThreatType,
          name: genEvent.name,
          startTime: genEvent.startTime,
          duration: genEvent.duration,
          severity: genEvent.severity,
          severityValue: genEvent.severityValue,
          difficulty: genEvent.difficulty,
          targetDevices: genEvent.targetDevices,
          description: genEvent.description,
          attackVector: genEvent.attackVector,
          indicators: genEvent.indicators,
          stageNumber: index + 1,
          dependsOn: index > 0 ? [events.value[events.value.length - 1].id] : undefined,
          successProbability: genEvent.successProbability || 80,
          isChainStart: index === 0,
        }
        events.value.push(newEvent)
        newChain.eventIds.push(newEvent.id)
      })

      attackChains.value.push(newChain)
      selectedChain.value = newChain

      // Show appropriate message based on verification status
      if (response.verified) {
        generationProgress.value = `Generated attack chain with ${response.events.length} stages!`
      } else {
        generationProgress.value = `Generated UNVERIFIED attack chain with ${response.events.length} stages (synthetic data)`
      }

      setTimeout(() => {
        showAIGenerator.value = false
        generationProgress.value = ''
        generationError.value = null
      }, 1500)
    } else {
      generationError.value = response.message || 'Failed to generate attack chain - no events returned'
      generationProgress.value = ''
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Generation failed'
    generationError.value = errorMsg
    generationProgress.value = ''
    // Refresh LLM status on error
    checkLLMStatus()
  } finally {
    isGenerating.value = false
  }
}

function toggleDeviceType(deviceType: string) {
  const index = aiConfig.value.deviceTypes.indexOf(deviceType)
  if (index > -1) {
    aiConfig.value.deviceTypes.splice(index, 1)
  } else {
    aiConfig.value.deviceTypes.push(deviceType)
  }
}

// ============== AI SCENARIO ANALYSIS FUNCTIONS ==============

async function analyzeCurrentScenario() {
  if (events.value.length === 0) {
    analysisResult.value = null
    return
  }

  isAnalyzing.value = true
  showAnalysisPanel.value = true

  try {
    // Convert events to the format expected by AgentService
    const eventsForAnalysis = events.value.map(e => ({
      id: e.id,
      type: e.type,
      name: e.name,
      startTime: e.startTime,
      duration: e.duration,
      severity: e.severity,
      severityValue: e.severityValue,
      difficulty: e.difficulty,
      targetDevices: e.targetDevices,
      description: e.description,
      attackVector: e.attackVector,
      indicators: e.indicators,
      stageNumber: e.stageNumber,
      dependsOn: e.dependsOn,
      successProbability: e.successProbability,
    }))

    const result = await agentService.analyzeScenario(eventsForAnalysis)
    analysisResult.value = result
  } catch (error) {
    console.error('Failed to analyze scenario:', error)
    analysisResult.value = {
      summary: 'Analysis failed. Please ensure the backend service is running.',
      riskScore: 0,
      vulnerabilities: [],
      attackPaths: [],
      recommendations: [],
      mitreCoverage: [],
    }
  } finally {
    isAnalyzing.value = false
  }
}

async function getDefenseSuggestions() {
  if (events.value.length === 0) return

  isAnalyzing.value = true

  try {
    const eventsForAnalysis = events.value.map(e => ({
      id: e.id,
      type: e.type,
      name: e.name,
      startTime: e.startTime,
      duration: e.duration,
      severity: e.severity,
      severityValue: e.severityValue,
      difficulty: e.difficulty,
      targetDevices: e.targetDevices,
      description: e.description,
      attackVector: e.attackVector,
      indicators: e.indicators,
    }))

    const suggestions = await agentService.suggestDefenses(eventsForAnalysis)

    // Merge suggestions into existing analysis
    if (analysisResult.value) {
      analysisResult.value.recommendations = suggestions
    } else {
      analysisResult.value = {
        summary: 'Defense suggestions for current scenario',
        riskScore: 50,
        vulnerabilities: [],
        attackPaths: [],
        recommendations: suggestions,
        mitreCoverage: [],
      }
    }
    showAnalysisPanel.value = true
  } catch (error) {
    console.error('Failed to get defense suggestions:', error)
  } finally {
    isAnalyzing.value = false
  }
}

function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'critical': return '#dc2626'
    case 'high': return '#f97316'
    case 'medium': return '#eab308'
    case 'low': return '#22c55e'
    default: return '#6b7280'
  }
}

function getRiskScoreColor(score: number): string {
  if (score >= 75) return '#dc2626'
  if (score >= 50) return '#f97316'
  if (score >= 25) return '#eab308'
  return '#22c55e'
}
</script>

<template>
  <div class="threat-builder">
    <!-- Header -->
    <div class="builder-header">
      <div class="header-left">
        <h2>Threat Builder</h2>
        <span class="stats">
          {{ totalThreats }} threats configured
        </span>
      </div>
      <div class="header-actions">
        <!-- Chain Mode Toggle -->
        <button
          class="btn"
          :class="isChainMode ? 'btn-primary' : 'btn-ghost'"
          @click="toggleChainMode"
          :title="isChainMode ? 'Exit chain mode' : 'Enter chain mode to link attacks'"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
          </svg>
          {{ isChainMode ? 'Exit Chain Mode' : 'Chain Mode' }}
        </button>
        <button class="btn btn-ghost" @click="createNewChain" title="Create new attack chain">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="16"></line>
            <line x1="8" y1="12" x2="16" y2="12"></line>
          </svg>
          New Chain
        </button>
        <button class="btn btn-ghost" @click="showChainBuilder = true" title="Open visual chain builder">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="6" height="6" rx="1"></rect>
            <rect x="15" y="3" width="6" height="6" rx="1"></rect>
            <rect x="9" y="15" width="6" height="6" rx="1"></rect>
            <line x1="9" y1="6" x2="15" y2="6"></line>
            <line x1="12" y1="9" x2="12" y2="15"></line>
          </svg>
          Chain Builder
        </button>
        <div class="header-divider"></div>
        <!-- AI Generation Button -->
        <button class="btn btn-accent" @click="openAIGenerator" title="Generate threats with AI">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path>
            <circle cx="7.5" cy="14.5" r="1.5"></circle>
            <circle cx="16.5" cy="14.5" r="1.5"></circle>
          </svg>
          AI Generate
        </button>
        <!-- AI Analysis Button -->
        <button
          class="btn btn-ghost"
          @click="analyzeCurrentScenario"
          :disabled="events.length === 0 || isAnalyzing"
          title="Analyze scenario with AI"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          {{ isAnalyzing ? 'Analyzing...' : 'Analyze' }}
        </button>
        <div class="header-divider"></div>
        <button class="btn btn-ghost" @click="zoomOut" title="Zoom out">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        <button class="btn btn-ghost" @click="zoomIn" title="Zoom in">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="11" y1="8" x2="11" y2="14"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>
        <button class="btn btn-ghost" @click="showScenarioBrowser = true" title="Browse preloaded scenarios">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
          </svg>
          Browse
        </button>
        <button class="btn btn-ghost" @click="clearAll">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          Clear
        </button>
        <button class="btn btn-ghost" @click="triggerScenarioLoad">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          Load
        </button>
        <button class="btn btn-primary" @click="saveScenario">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
            <polyline points="17 21 17 13 7 13 7 21"></polyline>
            <polyline points="7 3 7 8 15 8"></polyline>
          </svg>
          Save
        </button>
        <!-- Hidden file input for loading scenarios -->
        <input
          ref="scenarioFileInputRef"
          type="file"
          accept=".json"
          style="display: none"
          @change="handleScenarioLoad"
        />
      </div>
    </div>

    <!-- RESEARCH INTEGRITY: Unverified Data Warning Banner -->
    <div v-if="lastGenerationVerified === false" class="unverified-data-banner">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
      <div class="banner-content">
        <strong>UNVERIFIED DATA WARNING</strong>
        <span>
          This scenario contains synthetic (non-LLM generated) threat data.
          This data is suitable for demonstration and testing purposes only.
          <strong>Do NOT use for research conclusions or publications.</strong>
        </span>
      </div>
      <button class="dismiss-btn" @click="lastGenerationVerified = null" title="Dismiss warning">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>

    <div class="builder-content">
      <!-- Left Sidebar - Threat Palette -->
      <aside class="threat-palette">
        <div class="palette-header">
          <h4>Threat Types</h4>
        </div>
        <div class="threat-list">
          <button
            v-for="threat in threatTemplates"
            :key="threat.type"
            class="threat-item"
            @click="addThreatEvent(threat.type)"
          >
            <span class="threat-icon" :style="{ backgroundColor: `${threat.color}20`, color: threat.color }">
              {{ threat.icon }}
            </span>
            <div class="threat-info">
              <span class="threat-name">{{ threat.name }}</span>
              <span class="threat-desc">{{ threat.description }}</span>
            </div>
            <span class="severity-dot" :style="{ backgroundColor: getSeverityColor(threat.defaultSeverity) }"></span>
          </button>
        </div>

        <!-- Severity Summary -->
        <div class="severity-summary">
          <h4>Severity Distribution</h4>
          <div class="severity-bars">
            <div class="severity-row">
              <span class="severity-label">Critical</span>
              <div class="severity-bar">
                <div class="bar-fill critical" :style="{ width: `${(severityCounts.critical / Math.max(totalThreats, 1)) * 100}%` }"></div>
              </div>
              <span class="severity-count">{{ severityCounts.critical }}</span>
            </div>
            <div class="severity-row">
              <span class="severity-label">High</span>
              <div class="severity-bar">
                <div class="bar-fill high" :style="{ width: `${(severityCounts.high / Math.max(totalThreats, 1)) * 100}%` }"></div>
              </div>
              <span class="severity-count">{{ severityCounts.high }}</span>
            </div>
            <div class="severity-row">
              <span class="severity-label">Medium</span>
              <div class="severity-bar">
                <div class="bar-fill medium" :style="{ width: `${(severityCounts.medium / Math.max(totalThreats, 1)) * 100}%` }"></div>
              </div>
              <span class="severity-count">{{ severityCounts.medium }}</span>
            </div>
            <div class="severity-row">
              <span class="severity-label">Low</span>
              <div class="severity-bar">
                <div class="bar-fill low" :style="{ width: `${(severityCounts.low / Math.max(totalThreats, 1)) * 100}%` }"></div>
              </div>
              <span class="severity-count">{{ severityCounts.low }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Timeline -->
      <main class="timeline-area">
        <!-- Timeline Header (time markers) -->
        <div class="timeline-header">
          <div class="time-markers">
            <span
              v-for="hour in Math.ceil(simulationDuration / 60) + 1"
              :key="hour"
              class="time-marker"
              :style="{ left: `${((hour - 1) * 60 / simulationDuration) * 100}%` }"
            >
              {{ formatTime((hour - 1) * 60) }}
            </span>
          </div>
        </div>

        <!-- Timeline Canvas -->
        <div
          ref="timelineCanvasRef"
          class="timeline-canvas"
          :class="{ dragging: isDraggingEvent, resizing: isResizingEvent }"
        >
          <!-- Empty State -->
          <div v-if="events.length === 0" class="empty-timeline">
            <div class="empty-icon">🎯</div>
            <h3>Design Your Attack Scenario</h3>
            <p>Click on threat types from the palette to add them to the timeline</p>
          </div>

          <!-- Grid lines -->
          <div class="timeline-grid">
            <div
              v-for="hour in Math.ceil(simulationDuration / 60)"
              :key="hour"
              class="grid-line"
              :style="{ left: `${(hour * 60 / simulationDuration) * 100}%` }"
            ></div>
          </div>

          <!-- Chain Connection SVG Arrows (curved like Chain Builder) -->
          <svg class="chain-connections-svg" v-if="chainConnections.length > 0">
            <defs>
              <marker
                v-for="conn in chainConnections"
                :key="'marker-' + conn.from.id + '-' + conn.to.id"
                :id="'arrowhead-' + conn.from.id + '-' + conn.to.id"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" :fill="conn.color" />
              </marker>
            </defs>
            <path
              v-for="(conn, idx) in chainConnections"
              :key="'conn-' + idx"
              :d="getConnectionPath(conn)"
              fill="none"
              :stroke="conn.color"
              stroke-width="3"
              stroke-dasharray="8,4"
              :marker-end="'url(#arrowhead-' + conn.from.id + '-' + conn.to.id + ')'"
              class="connection-path"
            />
          </svg>

          <!-- Events -->
          <div
            v-for="(event, index) in sortedEvents"
            :key="event.id"
            class="timeline-event"
            :class="{
              selected: selectedEvent?.id === event.id,
              dragging: draggedEvent?.id === event.id,
              resizing: resizeEvent?.id === event.id,
              'chain-mode': isChainMode,
              'chain-link-source': chainLinkSource?.id === event.id,
              'in-chain': getEventChain(event.id) !== undefined
            }"
            :style="{
              ...getEventStyle(event),
              top: `${20 + (index % 4) * 70}px`,
              '--chain-color': getChainColor(event.id) || 'transparent'
            }"
            @mousedown="handleEventDragStart($event, event)"
            @click="isChainMode ? handleChainLinkClick(event) : selectEvent(event)"
          >
            <!-- Chain badge -->
            <div
              v-if="event.stageNumber"
              class="chain-badge"
              :style="{ backgroundColor: getChainColor(event.id) }"
              :title="'Stage ' + event.stageNumber + ' of ' + getEventChain(event.id)?.name"
            >
              {{ event.stageNumber }}
            </div>
            <div class="event-content">
              <span class="event-icon">{{ getThreatTemplate(event.type)?.icon }}</span>
              <span class="event-name">{{ event.name }}</span>
              <span class="event-time">{{ formatTime(event.startTime) }} - {{ formatTime(event.startTime + event.duration) }}</span>
            </div>
            <!-- Chain link button (visible in chain mode) -->
            <button
              v-if="isChainMode && selectedChain"
              class="chain-link-btn"
              @click.stop="addEventToChain(event)"
              :title="getEventChain(event.id) ? 'Already in chain' : 'Add to ' + selectedChain.name"
              :disabled="getEventChain(event.id) !== undefined"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
            </button>
            <button
              class="event-delete"
              @click.stop="deleteEvent(event.id)"
              title="Delete event"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
            <!-- Resize handle -->
            <div
              class="event-resize-handle"
              @mousedown="handleEventResizeStart($event, event)"
              title="Drag to resize duration"
            ></div>
          </div>

          <!-- Current time indicator -->
          <div
            class="time-indicator"
            :style="{ left: `${(currentTime / simulationDuration) * 100}%` }"
          ></div>
        </div>

        <!-- Timeline Controls -->
        <div class="timeline-controls">
          <div class="duration-control">
            <label>Simulation Duration:</label>
            <select v-model.number="simulationDuration" class="input">
              <option :value="60">1 Hour</option>
              <option :value="120">2 Hours</option>
              <option :value="240">4 Hours</option>
              <option :value="480">8 Hours</option>
              <option :value="720">12 Hours</option>
              <option :value="1440">24 Hours</option>
            </select>
          </div>
        </div>
      </main>

      <!-- Right Sidebar - Event Properties -->
      <aside class="properties-sidebar">
        <div v-if="selectedEvent" class="properties-panel">
          <h4>Event Properties</h4>

          <div class="property-group">
            <label>Name</label>
            <input
              type="text"
              class="input"
              v-model="selectedEvent.name"
            />
          </div>

          <div class="property-group">
            <label>Threat Type</label>
            <div
              class="type-badge"
              :style="{
                backgroundColor: `${getThreatTemplate(selectedEvent.type)?.color}20`,
                color: getThreatTemplate(selectedEvent.type)?.color
              }"
            >
              {{ getThreatTemplate(selectedEvent.type)?.icon }}
              {{ getThreatTemplate(selectedEvent.type)?.name }}
            </div>
          </div>

          <div class="property-group">
            <label>Start Time (minutes)</label>
            <input
              type="number"
              class="input"
              v-model.number="selectedEvent.startTime"
              :min="0"
              :max="simulationDuration - selectedEvent.duration"
            />
            <span class="input-hint">{{ formatTime(selectedEvent.startTime) }}</span>
          </div>

          <div class="property-group">
            <label>Duration (minutes)</label>
            <input
              type="number"
              class="input"
              v-model.number="selectedEvent.duration"
              :min="5"
              :max="simulationDuration - selectedEvent.startTime"
            />
          </div>

          <div class="property-group">
            <label>Severity</label>
            <div class="slider-container">
              <input
                type="range"
                class="slider severity-slider"
                :style="{
                  '--slider-color': getSeverityColor(selectedEvent.severity),
                  '--slider-progress': `${selectedEvent.severityValue}%`
                }"
                v-model.number="selectedEvent.severityValue"
                min="1"
                max="100"
                @input="updateSeverityFromSlider(selectedEvent)"
              />
              <div class="slider-labels">
                <span
                  class="slider-value"
                  :style="{ color: getSeverityColor(selectedEvent.severity) }"
                >
                  {{ selectedEvent.severity.toUpperCase() }}
                </span>
                <span class="slider-number">{{ selectedEvent.severityValue }}</span>
              </div>
              <div class="slider-markers">
                <span>Low</span>
                <span>Medium</span>
                <span>High</span>
                <span>Critical</span>
              </div>
            </div>
          </div>

          <div class="property-group">
            <label>Attack Difficulty</label>
            <div class="slider-container">
              <input
                type="range"
                class="slider difficulty-slider"
                :style="{
                  '--slider-color': getDifficultyColor(selectedEvent.difficulty),
                  '--slider-progress': `${selectedEvent.difficulty}%`
                }"
                v-model.number="selectedEvent.difficulty"
                min="1"
                max="100"
              />
              <div class="slider-labels">
                <span
                  class="slider-value"
                  :style="{ color: getDifficultyColor(selectedEvent.difficulty) }"
                >
                  {{ getDifficultyLabel(selectedEvent.difficulty) }}
                </span>
                <span class="slider-number">{{ selectedEvent.difficulty }}</span>
              </div>
              <div class="slider-markers">
                <span>Easy</span>
                <span>Medium</span>
                <span>Hard</span>
                <span>Expert</span>
              </div>
            </div>
          </div>

          <div class="property-group">
            <label>Description</label>
            <textarea
              class="input"
              v-model="selectedEvent.description"
              rows="3"
            ></textarea>
          </div>

          <div class="property-group">
            <label>MITRE ATT&CK Technique</label>
            <input
              type="text"
              class="input"
              v-model="selectedEvent.attackVector"
              placeholder="e.g., T1557"
            />
          </div>

          <!-- Chain Properties Section -->
          <div class="chain-properties" v-if="getEventChain(selectedEvent.id)">
            <h5>Attack Chain</h5>
            <div class="chain-info-card" :style="{ borderColor: getChainColor(selectedEvent.id) }">
              <div class="chain-info-header">
                <span class="chain-name">{{ getEventChain(selectedEvent.id)?.name }}</span>
                <span class="stage-badge" :style="{ backgroundColor: getChainColor(selectedEvent.id) }">
                  Stage {{ selectedEvent.stageNumber }}
                </span>
              </div>
              <div class="property-group">
                <label>Success Probability (%)</label>
                <input
                  type="range"
                  class="slider"
                  v-model.number="selectedEvent.successProbability"
                  min="0"
                  max="100"
                  :style="{
                    '--slider-color': getChainColor(selectedEvent.id),
                    '--slider-progress': `${selectedEvent.successProbability || 80}%`
                  }"
                />
                <span class="input-hint">{{ selectedEvent.successProbability || 80 }}%</span>
              </div>
              <button class="btn btn-ghost btn-sm" @click="removeEventFromChain(selectedEvent.id)">
                Remove from Chain
              </button>
            </div>
          </div>
          <div v-else-if="selectedChain" class="chain-add-prompt">
            <button class="btn btn-ghost btn-sm" @click="addEventToChain(selectedEvent)">
              Add to {{ selectedChain.name }}
            </button>
          </div>

          <!-- Preview Button -->
          <div class="preview-actions">
            <button class="btn btn-primary preview-btn" @click="startPreview(selectedEvent)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              Preview Threat
            </button>
          </div>
        </div>

        <!-- Chain Management Panel (when no event selected) -->
        <div v-else-if="attackChains.length > 0 || isChainMode" class="chain-management-panel">
          <h4>Attack Chains</h4>
          <p class="panel-hint" v-if="isChainMode">
            Click events on the timeline to add them to the selected chain
          </p>

          <div class="chain-list">
            <div
              v-for="chain in attackChains"
              :key="chain.id"
              class="chain-card"
              :class="{ selected: selectedChain?.id === chain.id }"
              :style="{ '--chain-color': chain.color }"
              @click="selectedChain = chain"
            >
              <div class="chain-card-header">
                <span class="chain-color-dot" :style="{ backgroundColor: chain.color }"></span>
                <input
                  type="text"
                  class="chain-name-input"
                  v-model="chain.name"
                  @click.stop
                />
                <button class="chain-delete-btn" @click.stop="deleteChain(chain.id)" title="Delete chain">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
              <div class="chain-card-body">
                <span class="chain-event-count">{{ chain.eventIds.length }} events</span>
                <div class="chain-event-preview">
                  <span
                    v-for="eventId in chain.eventIds.slice(0, 3)"
                    :key="eventId"
                    class="chain-event-dot"
                    :title="events.find(e => e.id === eventId)?.name"
                  >
                    {{ getThreatTemplate(events.find(e => e.id === eventId)?.type || 'man_in_the_middle')?.icon }}
                  </span>
                  <span v-if="chain.eventIds.length > 3" class="chain-more">+{{ chain.eventIds.length - 3 }}</span>
                </div>
              </div>
              <textarea
                v-if="selectedChain?.id === chain.id"
                class="chain-description input"
                v-model="chain.description"
                placeholder="Describe the attack chain..."
                rows="2"
                @click.stop
              ></textarea>
            </div>
          </div>

          <button v-if="attackChains.length === 0" class="btn btn-ghost create-chain-btn" @click="createNewChain">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="16"></line>
              <line x1="8" y1="12" x2="16" y2="12"></line>
            </svg>
            Create Your First Attack Chain
          </button>
        </div>

        <div v-else class="empty-properties">
          <p>Select a threat event to view and edit its properties</p>
          <p class="empty-hint">Or create an attack chain to link multiple events</p>
        </div>
      </aside>
    </div>

    <!-- Scenario Browser Modal -->
    <Teleport to="body">
      <div v-if="showScenarioBrowser" class="modal-overlay" @click.self="showScenarioBrowser = false">
        <div class="modal-container scenario-browser-modal">
          <ScenarioBrowser
            mode="threat"
            :show-preview="true"
            @load="loadPreloadedScenario"
            @close="showScenarioBrowser = false"
          />
        </div>
      </div>
    </Teleport>

    <!-- AI Generator Modal -->
    <Teleport to="body">
      <div v-if="showAIGenerator" class="modal-overlay" @click.self="!isGenerating && (showAIGenerator = false)">
        <div class="modal-container ai-generator-modal">
          <div class="ai-generator">
            <div class="ai-header">
              <div class="ai-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path>
                  <circle cx="7.5" cy="14.5" r="1.5"></circle>
                  <circle cx="16.5" cy="14.5" r="1.5"></circle>
                </svg>
                <h3>AI Threat Generator</h3>
              </div>
              <button class="close-btn" @click="showAIGenerator = false" :disabled="isGenerating">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="ai-body">
              <div class="ai-section">
                <h4>Home Configuration</h4>
                <div class="config-group">
                  <label>Home Type</label>
                  <select v-model="aiConfig.homeType" class="input" :disabled="isGenerating">
                    <option value="apartment">Apartment</option>
                    <option value="house">House</option>
                    <option value="smart_home">Smart Home</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                </div>
                <div class="config-group">
                  <label>Target Devices</label>
                  <div class="device-chips">
                    <button
                      v-for="device in ['smart_thermostat', 'smart_camera', 'smart_lock', 'smart_speaker', 'smart_light', 'smart_tv', 'smart_plug', 'smart_sensor']"
                      :key="device"
                      class="device-chip"
                      :class="{ active: aiConfig.deviceTypes.includes(device) }"
                      @click="toggleDeviceType(device)"
                      :disabled="isGenerating"
                    >
                      {{ device.replace('smart_', '').replace('_', ' ') }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="ai-section">
                <h4>Attack Parameters</h4>
                <div class="config-row">
                  <div class="config-group">
                    <label>Security Level</label>
                    <select v-model="aiConfig.securityLevel" class="input" :disabled="isGenerating">
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </div>
                  <div class="config-group">
                    <label>Attack Difficulty</label>
                    <select v-model="aiConfig.attackDifficulty" class="input" :disabled="isGenerating">
                      <option value="beginner">Beginner</option>
                      <option value="intermediate">Intermediate</option>
                      <option value="advanced">Advanced</option>
                      <option value="expert">Expert</option>
                    </select>
                  </div>
                </div>
                <div class="config-row">
                  <div class="config-group">
                    <label>Number of Events</label>
                    <input type="number" v-model.number="aiConfig.numEvents" class="input" min="1" max="20" :disabled="isGenerating" />
                  </div>
                  <div class="config-group">
                    <label>Duration (minutes)</label>
                    <input type="number" v-model.number="aiConfig.duration" class="input" min="60" max="1440" step="60" :disabled="isGenerating" />
                  </div>
                </div>
              </div>

              <!-- RESEARCH INTEGRITY: Unverified Mode Toggle -->
              <div class="ai-section research-integrity-section">
                <h4>Research Integrity</h4>
                <div class="unverified-toggle">
                  <label class="toggle-label" :class="{ 'is-checked': allowUnverifiedMode }">
                    <input
                      type="checkbox"
                      v-model="allowUnverifiedMode"
                      :disabled="isGenerating"
                      class="toggle-input"
                    />
                    <span class="toggle-slider"></span>
                    <span class="toggle-text">Allow Unverified Mode</span>
                  </label>
                  <p class="toggle-description">
                    When enabled, synthetic (non-LLM) data may be used if the AI service is unavailable.
                    <strong>This data is NOT suitable for research conclusions.</strong>
                  </p>
                </div>
                <div v-if="allowUnverifiedMode" class="unverified-warning">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  <span>
                    WARNING: You have acknowledged that unverified synthetic data may be generated.
                    Results will be clearly marked and should NOT be used for research publications.
                  </span>
                </div>
              </div>

              <!-- LLM Status Indicator -->
              <div class="llm-status-section">
                <div class="llm-status-indicator" :class="{ available: isLLMAvailable, unavailable: isLLMAvailable === false, checking: isCheckingLLM }">
                  <span v-if="isCheckingLLM" class="spinner-small"></span>
                  <svg v-else-if="isLLMAvailable" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                  </svg>
                  <svg v-else-if="isLLMAvailable === false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                  </svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                  <span class="llm-status-text">
                    {{ isCheckingLLM ? 'Checking LLM...' : isLLMAvailable ? 'Ollama LLM Available' : isLLMAvailable === false ? 'Ollama LLM Unavailable' : 'LLM Status Unknown' }}
                  </span>
                  <button v-if="!isCheckingLLM" class="refresh-btn" @click="checkLLMStatus" title="Refresh LLM status">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M23 4v6h-6"></path>
                      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Error Display -->
              <div v-if="generationError" class="error-section">
                <div class="error-message">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                  <div class="error-content">
                    <strong>Generation Failed</strong>
                    <p>{{ generationError }}</p>
                  </div>
                  <button class="dismiss-btn" @click="dismissError" title="Dismiss error">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </button>
                </div>
                <div class="error-actions">
                  <button class="btn btn-ghost btn-sm" @click="retryGeneration">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M23 4v6h-6"></path>
                      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                    Retry
                  </button>
                  <button v-if="!allowUnverifiedMode && isLLMAvailable === false" class="btn btn-warning btn-sm" @click="allowUnverifiedMode = true">
                    Enable Synthetic Fallback
                  </button>
                </div>
              </div>

              <!-- Progress indicator -->
              <div v-if="generationProgress && !generationError" class="progress-section">
                <div class="progress-indicator">
                  <span v-if="isGenerating" class="spinner-small"></span>
                  <span class="progress-text">{{ generationProgress }}</span>
                </div>
              </div>
            </div>

            <div class="ai-footer">
              <button class="btn btn-ghost" @click="showAIGenerator = false" :disabled="isGenerating">
                Cancel
              </button>
              <button class="btn btn-ghost" @click="generateAIAttackChain" :disabled="isGenerating">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
                Generate Chain
              </button>
              <button class="btn btn-primary" @click="generateAIThreats" :disabled="isGenerating">
                <svg v-if="!isGenerating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <span v-else class="spinner-small"></span>
                {{ isGenerating ? 'Generating...' : 'Generate Threats' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Attack Chain Builder Modal -->
    <Teleport to="body">
      <div v-if="showChainBuilder" class="modal-overlay" @click.self="showChainBuilder = false">
        <div class="modal-container chain-builder-modal">
          <AttackChainBuilder
            :events="events as any"
            :chains="attackChains"
            :selected-chain="selectedChain"
            @update:chains="newChains => attackChains = newChains"
            @update:selected-chain="chain => selectedChain = chain"
            @add-event-to-chain="(event: any, chain: AttackChain) => addEventToChain(event as ThreatEvent, chain)"
            @remove-event-from-chain="removeEventFromChain"
            @create-chain="createNewChain"
            @delete-chain="deleteChain"
            @close="showChainBuilder = false"
          />
        </div>
      </div>
    </Teleport>

    <!-- AI Analysis Panel -->
    <Teleport to="body">
      <div v-if="showAnalysisPanel" class="modal-overlay" @click.self="showAnalysisPanel = false">
        <div class="modal-container analysis-panel-modal">
          <div class="analysis-panel">
            <div class="analysis-header">
              <div class="analysis-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <h3>Scenario Analysis</h3>
              </div>
              <button class="close-btn" @click="showAnalysisPanel = false">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="analysis-body" v-if="analysisResult">
              <!-- Risk Score -->
              <div class="risk-score-section">
                <div class="risk-gauge">
                  <svg viewBox="0 0 100 60" class="gauge-svg">
                    <path
                      d="M 10,50 A 40,40 0 0,1 90,50"
                      fill="none"
                      stroke="var(--border-color)"
                      stroke-width="8"
                      stroke-linecap="round"
                    />
                    <path
                      d="M 10,50 A 40,40 0 0,1 90,50"
                      fill="none"
                      :stroke="getRiskScoreColor(analysisResult.riskScore)"
                      stroke-width="8"
                      stroke-linecap="round"
                      :stroke-dasharray="`${analysisResult.riskScore * 1.26} 126`"
                    />
                  </svg>
                  <div class="risk-value" :style="{ color: getRiskScoreColor(analysisResult.riskScore) }">
                    {{ analysisResult.riskScore }}
                  </div>
                  <div class="risk-label">Risk Score</div>
                </div>
              </div>

              <!-- Summary -->
              <div class="analysis-section">
                <h4>Summary</h4>
                <p class="analysis-summary">{{ analysisResult.summary }}</p>
              </div>

              <!-- Vulnerabilities -->
              <div class="analysis-section" v-if="analysisResult.vulnerabilities.length > 0">
                <h4>Vulnerabilities</h4>
                <div class="tag-list">
                  <span v-for="vuln in analysisResult.vulnerabilities" :key="vuln" class="vuln-tag">
                    {{ vuln }}
                  </span>
                </div>
              </div>

              <!-- Attack Paths -->
              <div class="analysis-section" v-if="analysisResult.attackPaths.length > 0">
                <h4>Potential Attack Paths</h4>
                <ul class="attack-paths">
                  <li v-for="path in analysisResult.attackPaths" :key="path">{{ path }}</li>
                </ul>
              </div>

              <!-- MITRE Coverage -->
              <div class="analysis-section" v-if="analysisResult.mitreCoverage.length > 0">
                <h4>MITRE ATT&CK Coverage</h4>
                <div class="mitre-tags">
                  <span v-for="tech in analysisResult.mitreCoverage" :key="tech" class="mitre-tag">
                    {{ tech }}
                  </span>
                </div>
              </div>

              <!-- Recommendations -->
              <div class="analysis-section" v-if="analysisResult.recommendations.length > 0">
                <h4>Defense Recommendations</h4>
                <div class="recommendations-list">
                  <div
                    v-for="rec in analysisResult.recommendations"
                    :key="rec.id"
                    class="recommendation-card"
                    :style="{ '--priority-color': getPriorityColor(rec.priority) }"
                  >
                    <div class="rec-header">
                      <span class="rec-title">{{ rec.title }}</span>
                      <span class="rec-priority" :style="{ backgroundColor: getPriorityColor(rec.priority) }">
                        {{ rec.priority }}
                      </span>
                    </div>
                    <p class="rec-description">{{ rec.description }}</p>
                    <div class="rec-mitigates" v-if="rec.mitigates.length > 0">
                      <span class="mitigates-label">Mitigates:</span>
                      <span v-for="threat in rec.mitigates" :key="threat" class="mitigate-tag">{{ threat }}</span>
                    </div>
                    <div class="rec-effort">
                      <span>Effort: {{ rec.estimatedEffort }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="analysis-body" v-else-if="isAnalyzing">
              <div class="loading-state">
                <span class="spinner-small"></span>
                <span>Analyzing scenario...</span>
              </div>
            </div>

            <div class="analysis-body" v-else>
              <div class="empty-state">
                <p>No analysis available. Add threat events and click Analyze.</p>
              </div>
            </div>

            <div class="analysis-footer">
              <button class="btn btn-ghost" @click="getDefenseSuggestions" :disabled="isAnalyzing || events.length === 0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                Get Defense Suggestions
              </button>
              <button class="btn btn-primary" @click="showAnalysisPanel = false">
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Threat Preview Modal -->
    <Teleport to="body">
      <div v-if="showPreview" class="modal-overlay preview-overlay" @click.self="stopPreview">
        <div class="modal-container preview-modal">
          <div class="preview-panel">
            <div class="preview-header">
              <div class="preview-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                <h3>Threat Preview</h3>
              </div>
              <button class="btn btn-ghost btn-sm" @click="stopPreview">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="preview-body">
              <!-- Phase Indicator -->
              <div class="phase-indicator">
                <div class="phase" :class="{ active: previewPhase === 'initializing', completed: ['executing', 'propagating', 'complete'].includes(previewPhase) }">
                  <div class="phase-icon">1</div>
                  <span>Initialize</span>
                </div>
                <div class="phase-connector" :class="{ active: ['executing', 'propagating', 'complete'].includes(previewPhase) }"></div>
                <div class="phase" :class="{ active: previewPhase === 'executing', completed: ['propagating', 'complete'].includes(previewPhase) }">
                  <div class="phase-icon">2</div>
                  <span>Execute</span>
                </div>
                <div class="phase-connector" :class="{ active: ['propagating', 'complete'].includes(previewPhase) }"></div>
                <div class="phase" :class="{ active: previewPhase === 'propagating', completed: previewPhase === 'complete' }">
                  <div class="phase-icon">3</div>
                  <span>Propagate</span>
                </div>
                <div class="phase-connector" :class="{ active: previewPhase === 'complete' }"></div>
                <div class="phase" :class="{ active: previewPhase === 'complete' }">
                  <div class="phase-icon">✓</div>
                  <span>Complete</span>
                </div>
              </div>

              <!-- Progress Bar -->
              <div class="preview-progress">
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: previewProgress + '%' }"></div>
                </div>
                <span class="progress-label">{{ Math.round(previewProgress) }}%</span>
              </div>

              <!-- Preview Logs -->
              <div class="preview-logs">
                <div class="logs-header">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                  <span>Execution Log</span>
                </div>
                <div class="logs-content">
                  <div
                    v-for="(log, index) in previewLogs"
                    :key="index"
                    class="log-entry"
                    :class="'log-' + log.type"
                  >
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-type-badge">{{ log.type.toUpperCase() }}</span>
                    <span class="log-message">{{ log.message }}</span>
                  </div>
                  <div v-if="previewLogs.length === 0" class="empty-logs">
                    Waiting for execution...
                  </div>
                </div>
              </div>
            </div>

            <div class="preview-footer">
              <button class="btn btn-ghost" @click="stopPreview">
                {{ previewPhase === 'complete' ? 'Close' : 'Stop Preview' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.threat-builder {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  min-height: 500px;
}

.builder-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--spacing-md);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-md);
}

.header-left h2 {
  margin: 0;
}

.stats {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.header-actions .btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.builder-content {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  gap: var(--spacing-md);
  flex: 1;
  overflow: hidden;
}

/* Threat Palette */
.threat-palette {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.palette-header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.palette-header h4 {
  margin: 0;
  font-size: 0.875rem;
}

.threat-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.threat-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  margin-bottom: var(--spacing-xs);
  transition: all var(--transition-fast);
}

.threat-item:hover {
  border-color: var(--color-primary);
}

.threat-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 1rem;
}

.threat-info {
  flex: 1;
  min-width: 0;
}

.threat-name {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
}

.threat-desc {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

/* Severity Summary */
.severity-summary {
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.severity-summary h4 {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
}

.severity-bars {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.severity-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.severity-label {
  width: 50px;
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.severity-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-input);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width var(--transition-normal);
}

.bar-fill.critical { background: #dc2626; }
.bar-fill.high { background: #f97316; }
.bar-fill.medium { background: #eab308; }
.bar-fill.low { background: #22c55e; }

.severity-count {
  width: 20px;
  font-size: 0.7rem;
  color: var(--text-muted);
  text-align: right;
}

/* Timeline Area */
.timeline-area {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.timeline-header {
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  position: relative;
  height: 30px;
}

.time-markers {
  position: relative;
  height: 100%;
}

.time-marker {
  position: absolute;
  font-size: 0.65rem;
  color: var(--text-muted);
  transform: translateX(-50%);
}

.timeline-canvas {
  flex: 1;
  position: relative;
  overflow-x: auto;
  overflow-y: hidden;
  background: var(--bg-input);
  min-height: 300px;
}

.empty-timeline {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.empty-timeline h3 {
  margin-bottom: var(--spacing-sm);
  color: var(--text-primary);
}

.timeline-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.grid-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border-color);
}

.timeline-event {
  position: absolute;
  height: 60px;
  border: 2px solid;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: box-shadow var(--transition-fast);
  min-width: 80px;
}

.timeline-event:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.timeline-event.selected {
  box-shadow: 0 0 0 2px var(--color-primary);
}

.event-content {
  padding: var(--spacing-xs) var(--spacing-sm);
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.event-icon {
  font-size: 1rem;
  margin-bottom: 2px;
}

.event-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 0 2px rgba(255, 255, 255, 0.8);
}

.event-time {
  font-size: 0.65rem;
  font-weight: 500;
  color: #2d2d44;
  text-shadow: 0 0 2px rgba(255, 255, 255, 0.8);
}

.event-delete {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 16px;
  height: 16px;
  background: var(--color-error);
  color: white;
  border: none;
  border-radius: 50%;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 0.6rem;
}

.timeline-event:hover .event-delete {
  display: flex;
}

/* Event resize handle */
.event-resize-handle {
  position: absolute;
  right: -4px;
  top: 10%;
  bottom: 10%;
  width: 8px;
  cursor: ew-resize;
  background: transparent;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.timeline-event:hover .event-resize-handle,
.timeline-event.selected .event-resize-handle {
  opacity: 1;
  background: var(--color-primary);
  border-radius: 2px;
}

.event-resize-handle:hover {
  opacity: 1 !important;
}

/* Drag and resize states */
.timeline-canvas.dragging {
  cursor: grabbing;
}

.timeline-canvas.resizing {
  cursor: ew-resize;
}

.timeline-event {
  cursor: grab;
}

.timeline-event:active {
  cursor: grabbing;
}

.timeline-event.dragging {
  opacity: 0.9;
  z-index: 100;
  cursor: grabbing;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.timeline-event.resizing {
  z-index: 100;
  box-shadow: 0 0 0 2px var(--color-primary);
}

.time-indicator {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--color-primary);
  z-index: 10;
}

.timeline-controls {
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

.duration-control {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.duration-control label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.duration-control .input {
  width: 120px;
}

/* Properties Sidebar */
.properties-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow-y: auto;
}

.properties-panel {
  padding: var(--spacing-md);
}

.properties-panel h4 {
  margin-bottom: var(--spacing-md);
  font-size: 0.9rem;
}

.property-group {
  margin-bottom: var(--spacing-md);
}

.property-group label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.property-group .input {
  width: 100%;
}

.property-group textarea.input {
  resize: vertical;
}

.input-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
}

/* Slider Styles */
.slider-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(
    to right,
    var(--slider-color, var(--color-primary)) 0%,
    var(--slider-color, var(--color-primary)) var(--slider-progress, 50%),
    var(--bg-input) var(--slider-progress, 50%),
    var(--bg-input) 100%
  );
  outline: none;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  border: 3px solid var(--slider-color, var(--color-primary));
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3);
}

.slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  border: 3px solid var(--slider-color, var(--color-primary));
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-value {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.slider-number {
  font-size: 0.7rem;
  color: var(--text-muted);
  background: var(--bg-input);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.slider-markers {
  display: flex;
  justify-content: space-between;
  font-size: 0.6rem;
  color: var(--text-muted);
  padding: 0 2px;
}

.empty-properties {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1024px) {
  .builder-content {
    grid-template-columns: 220px 1fr;
  }

  .properties-sidebar {
    display: none;
  }
}

@media (max-width: 768px) {
  .builder-content {
    grid-template-columns: 1fr;
  }

  .threat-palette {
    display: none;
  }
}

/* Modal Styles */
.modal-overlay {
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
  padding: var(--spacing-lg);
}

.modal-container {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  max-width: 1200px;
  width: 100%;
  max-height: 80vh;
  overflow: hidden;
}

.scenario-browser-modal {
  height: 75vh;
}

/* Header divider */
.header-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
  margin: 0 var(--spacing-xs);
}

/* Chain Connection SVG */
.chain-connections-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 5;
  overflow: visible;
}

.connection-path {
  animation: dash 0.5s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -12;
  }
}

/* Chain Badge on Events */
.chain-badge {
  position: absolute;
  top: -8px;
  left: -8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 700;
  color: white;
  z-index: 10;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* Chain Mode Event Styles */
.timeline-event.chain-mode {
  cursor: pointer;
}

.timeline-event.chain-mode:hover {
  transform: scale(1.02);
}

.timeline-event.chain-link-source {
  box-shadow: 0 0 0 3px var(--color-primary), 0 0 12px rgba(99, 102, 241, 0.4);
  animation: pulse-chain 1.5s ease-in-out infinite;
}

@keyframes pulse-chain {
  0%, 100% { box-shadow: 0 0 0 3px var(--color-primary), 0 0 12px rgba(99, 102, 241, 0.4); }
  50% { box-shadow: 0 0 0 5px var(--color-primary), 0 0 20px rgba(99, 102, 241, 0.6); }
}

.timeline-event.in-chain {
  border-left: 4px solid var(--chain-color);
}

/* Chain Link Button on Events */
.chain-link-btn {
  position: absolute;
  top: -6px;
  right: 16px;
  width: 18px;
  height: 18px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.timeline-event.chain-mode:hover .chain-link-btn {
  opacity: 1;
}

.chain-link-btn:disabled {
  background: var(--text-muted);
  cursor: not-allowed;
}

/* Chain Properties in Sidebar */
.chain-properties {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.chain-properties h5 {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.chain-info-card {
  background: var(--bg-input);
  border: 2px solid;
  border-radius: var(--radius-md);
  padding: var(--spacing-sm);
}

.chain-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.chain-info-header .chain-name {
  font-weight: 500;
  font-size: 0.85rem;
}

.stage-badge {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  color: white;
  font-size: 0.7rem;
  font-weight: 600;
}

.chain-add-prompt {
  margin-top: var(--spacing-md);
  text-align: center;
}

/* Chain Management Panel */
.chain-management-panel {
  padding: var(--spacing-md);
}

.chain-management-panel h4 {
  margin-bottom: var(--spacing-sm);
  font-size: 0.9rem;
}

.panel-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-primary);
}

.chain-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.chain-card {
  background: var(--bg-input);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  padding: var(--spacing-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chain-card:hover {
  border-color: var(--chain-color);
}

.chain-card.selected {
  border-color: var(--chain-color);
  background: linear-gradient(135deg, var(--bg-input), color-mix(in srgb, var(--chain-color) 10%, var(--bg-input)));
}

.chain-card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.chain-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chain-name-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 500;
  padding: 2px 4px;
  border-radius: var(--radius-sm);
}

.chain-name-input:focus {
  outline: none;
  background: var(--bg-card);
}

.chain-delete-btn {
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

.chain-card:hover .chain-delete-btn {
  opacity: 1;
}

.chain-delete-btn:hover {
  background: var(--color-error);
  color: white;
}

.chain-card-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chain-event-count {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.chain-event-preview {
  display: flex;
  gap: 2px;
  align-items: center;
}

.chain-event-dot {
  font-size: 0.75rem;
}

.chain-more {
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-left: 4px;
}

.chain-description {
  margin-top: var(--spacing-sm);
  width: 100%;
  font-size: 0.75rem;
  resize: none;
}

.create-chain-btn {
  width: 100%;
  margin-top: var(--spacing-md);
  justify-content: center;
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.75rem;
}

.empty-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: var(--spacing-sm);
}

/* Accent Button */
.btn-accent {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  color: white;
  border: none;
}

.btn-accent:hover {
  background: linear-gradient(135deg, #7c3aed, #4f46e5);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
}

/* AI Generator Modal */
.ai-generator-modal {
  max-width: 600px;
  max-height: 90vh; /* Override default 80vh to fit more content */
  display: flex;
  flex-direction: column;
}

.ai-generator {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0; /* Important for flex child scrolling */
  overflow: hidden;
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(99, 102, 241, 0.1));
}

.ai-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  color: var(--color-primary);
}

.ai-title h3 {
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

.close-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ai-body {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  min-height: 0; /* Important for flex child scrolling */
}

.ai-section h4 {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-group {
  margin-bottom: var(--spacing-md);
}

.config-group label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.config-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

.device-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.device-chip {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-transform: capitalize;
}

.device-chip:hover {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.device-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.device-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* LLM Status Indicator */
.llm-status-section {
  margin-bottom: var(--spacing-md);
}

.llm-status-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  border-left: 3px solid var(--text-muted);
}

.llm-status-indicator.available {
  border-left-color: var(--color-success, #22c55e);
  color: var(--color-success, #22c55e);
}

.llm-status-indicator.unavailable {
  border-left-color: var(--color-error, #dc2626);
  color: var(--color-error, #dc2626);
}

.llm-status-indicator.checking {
  border-left-color: var(--color-warning, #eab308);
  color: var(--color-warning, #eab308);
}

.llm-status-text {
  flex: 1;
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.refresh-btn:hover {
  background: var(--bg-card);
  color: var(--text-primary);
}

/* Error Display Styles */
.error-section {
  margin-bottom: var(--spacing-md);
}

.error-message {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(220, 38, 38, 0.1);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--color-error, #dc2626);
}

.error-message > svg {
  flex-shrink: 0;
  color: var(--color-error, #dc2626);
}

.error-content {
  flex: 1;
  min-width: 0;
}

.error-content strong {
  display: block;
  color: var(--color-error, #dc2626);
  font-size: 0.9rem;
  margin-bottom: var(--spacing-xs);
}

.error-content p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
  word-wrap: break-word;
}

.dismiss-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dismiss-btn:hover {
  background: rgba(220, 38, 38, 0.2);
  color: var(--color-error);
}

.error-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
  padding-left: calc(20px + var(--spacing-sm));
}

.btn-warning {
  background: rgba(234, 179, 8, 0.2);
  color: var(--color-warning, #eab308);
  border: 1px solid var(--color-warning, #eab308);
}

.btn-warning:hover {
  background: rgba(234, 179, 8, 0.3);
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.75rem;
}

.progress-section {
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--color-primary);
}

.progress-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.progress-text {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.ai-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
}

/* ============================================================
   RESEARCH INTEGRITY STYLES
   ============================================================ */

/* Toggle for unverified mode */
.research-integrity-section {
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-lg);
}

.unverified-toggle {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  user-select: none;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.toggle-slider {
  display: inline-block;
  width: 44px;
  height: 24px;
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  position: relative;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.toggle-slider::after {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  background: var(--text-muted);
  border-radius: 50%;
  top: 1px;
  left: 1px;
  transition: all 0.2s ease;
}

/* When toggle is checked - use Vue class binding */
.toggle-label.is-checked .toggle-slider {
  background: #f97316;
  border-color: #f97316;
}

.toggle-label.is-checked .toggle-slider::after {
  background: white;
  transform: translateX(20px);
}

/* Hover state */
.toggle-label:hover .toggle-slider {
  border-color: var(--color-primary);
}

.toggle-label.is-checked:hover .toggle-slider {
  border-color: #ea580c;
}

.toggle-text {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
}

.toggle-description {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
  margin: 0;
}

.toggle-description strong {
  color: #f97316;
}

/* Warning box when unverified mode is enabled */
.unverified-warning {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(249, 115, 22, 0.1);
  border: 1px solid #f97316;
  border-radius: var(--radius-md);
  margin-top: var(--spacing-md);
}

.unverified-warning svg {
  flex-shrink: 0;
  color: #f97316;
}

.unverified-warning span {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* Main banner for unverified data */
.unverified-data-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  background: linear-gradient(90deg, rgba(249, 115, 22, 0.15), rgba(239, 68, 68, 0.1));
  border-bottom: 2px solid #f97316;
  animation: pulse-warning 2s ease-in-out infinite;
}

@keyframes pulse-warning {
  0%, 100% { background: linear-gradient(90deg, rgba(249, 115, 22, 0.15), rgba(239, 68, 68, 0.1)); }
  50% { background: linear-gradient(90deg, rgba(249, 115, 22, 0.2), rgba(239, 68, 68, 0.15)); }
}

.unverified-data-banner svg {
  flex-shrink: 0;
  color: #f97316;
}

.unverified-data-banner .banner-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.unverified-data-banner .banner-content strong {
  color: #f97316;
  font-size: 0.9rem;
  font-weight: 600;
}

.unverified-data-banner .banner-content span {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.unverified-data-banner .banner-content span strong {
  color: #ef4444;
}

.unverified-data-banner .dismiss-btn {
  padding: var(--spacing-xs);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.unverified-data-banner .dismiss-btn:hover {
  background: rgba(0, 0, 0, 0.1);
  color: var(--text-primary);
}

/* Chain Builder Modal */
.chain-builder-modal {
  width: 95vw;
  max-width: 1400px;
  height: 80vh;
  max-height: 800px;
}

/* ============================================================
   AI ANALYSIS PANEL STYLES
   ============================================================ */

.analysis-panel-modal {
  max-width: 700px;
  max-height: 85vh;
}

.analysis-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 85vh;
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(20, 184, 166, 0.1));
}

.analysis-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  color: #22c55e;
}

.analysis-title h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.analysis-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

/* Risk Score Gauge */
.risk-score-section {
  display: flex;
  justify-content: center;
  padding: var(--spacing-lg) 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
}

.risk-gauge {
  position: relative;
  width: 180px;
  text-align: center;
}

.gauge-svg {
  width: 100%;
  height: auto;
}

.risk-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -20%);
  font-size: 2rem;
  font-weight: 700;
}

.risk-label {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: var(--spacing-xs);
}

/* Analysis Sections */
.analysis-section {
  margin-bottom: var(--spacing-lg);
}

.analysis-section h4 {
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--spacing-sm);
}

.analysis-summary {
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-primary);
  margin: 0;
}

/* Tags */
.tag-list,
.mitre-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.vuln-tag {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 500;
}

.mitre-tag {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-family: monospace;
}

/* Attack Paths */
.attack-paths {
  margin: 0;
  padding-left: var(--spacing-lg);
}

.attack-paths li {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

/* Recommendations */
.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.recommendation-card {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-left: 4px solid var(--priority-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.rec-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.rec-priority {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  color: white;
}

.rec-description {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-sm) 0;
  line-height: 1.5;
}

.rec-mitigates {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
}

.mitigates-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.mitigate-tag {
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.rec-effort {
  font-size: 0.7rem;
  color: var(--text-muted);
}

/* Loading & Empty States */
.loading-state,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

/* Footer */
.analysis-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
}

/* ============================================================
   THREAT PREVIEW STYLES
   ============================================================ */

.preview-overlay {
  background: rgba(0, 0, 0, 0.7);
}

.preview-modal {
  max-width: 600px;
  max-height: 80vh;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 80vh;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(249, 115, 22, 0.1));
}

.preview-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  color: #ef4444;
}

.preview-title h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.preview-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* Phase Indicator */
.phase-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: var(--spacing-md) 0;
}

.phase {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  opacity: 0.4;
  transition: all 0.3s ease;
}

.phase.active {
  opacity: 1;
}

.phase.active .phase-icon {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
  animation: pulse-phase 1s ease-in-out infinite;
}

.phase.completed {
  opacity: 1;
}

.phase.completed .phase-icon {
  background: #22c55e;
  border-color: #22c55e;
  color: white;
}

@keyframes pulse-phase {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.phase-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-muted);
  transition: all 0.3s ease;
}

.phase span {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.phase.active span,
.phase.completed span {
  color: var(--text-primary);
}

.phase-connector {
  width: 40px;
  height: 2px;
  background: var(--border-color);
  margin: 0 var(--spacing-xs);
  margin-bottom: 20px;
  transition: all 0.3s ease;
}

.phase-connector.active {
  background: #22c55e;
}

/* Progress Bar */
.preview-progress {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.preview-progress .progress-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.preview-progress .progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ef4444, #f97316);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.progress-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 45px;
  text-align: right;
}

/* Preview Logs */
.preview-logs {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.logs-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.logs-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
  max-height: 200px;
  font-family: monospace;
  font-size: 0.8rem;
}

.log-entry {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  margin-bottom: 2px;
}

.log-entry:last-child {
  margin-bottom: 0;
}

.log-time {
  color: var(--text-muted);
  min-width: 65px;
}

.log-type-badge {
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 600;
  min-width: 55px;
  text-align: center;
}

.log-message {
  color: var(--text-primary);
  flex: 1;
}

.log-info .log-type-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.log-warning .log-type-badge {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.log-danger .log-type-badge {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.log-success .log-type-badge {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.empty-logs {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: var(--text-muted);
  font-style: italic;
}

.preview-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
}

/* Preview button in properties panel */
.preview-actions {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.preview-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
}
</style>
