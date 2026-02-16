<script setup lang="ts">
import { ref, computed, onUnmounted, watch, onMounted } from 'vue'
import { scenarioManager, type ThreatScenario as PreloadedThreatScenario, type HomeScenario as PreloadedHomeScenario } from '@/services/PreloadedScenarioManager'
import { simulationApi, convertHomeConfigToBackend, type SimulationEvent as BackendSimEvent } from '@/services/simulationApi'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()

// ============== TYPES ==============

interface Device {
  id: string
  name: string
  type: string
  icon: string
  x: number
  y: number
  status: 'normal' | 'warning' | 'compromised' | 'offline'
}

interface Room {
  id: string
  name: string
  type: string
  x: number
  y: number
  width: number
  height: number
  devices: Device[]
}

interface Inhabitant {
  id: string
  name: string
  role: string
  icon: string
  currentRoom?: string
}

interface HomeConfig {
  rooms: Room[]
  inhabitants: Inhabitant[]
  createdAt?: string
}

interface ThreatEvent {
  id: string
  type: string
  name: string
  startTime: number
  duration: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  severityValue: number
  targetDevices: string[]
  description: string
  attackVector: string
  indicators: string[]
  status: 'pending' | 'active' | 'completed' | 'detected' | 'blocked'
}

interface ThreatScenario {
  id: string
  name: string
  events: ThreatEvent[]
  simulationDuration: number
}

interface SimulationEvent {
  id: string
  timestamp: number
  type: 'info' | 'warning' | 'attack' | 'detection' | 'system'
  message: string
  deviceId?: string
  threatId?: string
}

type SimulationState = 'idle' | 'running' | 'paused' | 'completed'
type SimulationMode = 'benign' | 'threat'

// ============== STATE ==============

// Home configuration
const homeConfig = ref<HomeConfig | null>(null)
const threatScenario = ref<ThreatScenario | null>(null)
const simulationMode = ref<SimulationMode>('benign')

// Simulation state
const simulationState = ref<SimulationState>('idle')
const currentTime = ref(0) // in minutes
const simulationDuration = ref(30) // 30 min default (in minutes)

// Speed multiplier: 1x = real-time, 2x = 2× faster, etc.
// At 1x: 1 simulated minute = 1 real minute
// At 2x: 1 simulated minute = 30 real seconds
// At 10x: 1 simulated minute = 6 real seconds
const simulationSpeed = ref(1)

// Custom duration/speed UI state
const showCustomDurationDialog = ref(false)
const customDurationSeconds = ref(3600) // Default 1 hour in seconds
const showCustomSpeedInput = ref(false)
const customSpeedValue = ref(100) // For custom speed input

// Event log
const eventLog = ref<SimulationEvent[]>([])
const maxLogEvents = 100

// Statistics
const stats = ref({
  totalEvents: 0,
  detectedThreats: 0,
  blockedThreats: 0,
  compromisedDevices: 0,
  alertsGenerated: 0,
})

// Save as Experiment state
const showSaveModal = ref(false)
const saveForm = ref({
  name: '',
  description: '',
  tags: '',
})
const isSaving = ref(false)
const saveError = ref('')
const saveSuccess = ref(false)

// Interval for simulation
let simulationInterval: ReturnType<typeof setInterval> | null = null
let backendPollInterval: ReturnType<typeof setInterval> | null = null

// Backend simulation state
const useBackendSimulation = ref(true) // Toggle to use backend SimulationEngine
const backendSimulationId = ref<string | null>(null)
const backendEvents = ref<BackendSimEvent[]>([])
const lastEventCount = ref(0)
const backendCompletionLogged = ref(false) // Flag to prevent duplicate completion messages
const simulationStartTime = ref<string | null>(null) // ISO timestamp when simulation started

// Preloaded scenarios
const preloadedThreatScenarios = ref<PreloadedThreatScenario[]>([])
const preloadedHomeScenarios = ref<PreloadedHomeScenario[]>([])
const showThreatPicker = ref(false)
const showHomePicker = ref(false)

// Load chat-created scenario from sessionStorage
async function loadChatCreatedScenario(): Promise<boolean> {
  const homeStr = sessionStorage.getItem('chatCreatedHome')
  const threatStr = sessionStorage.getItem('chatCreatedThreat')
  const scenarioStr = sessionStorage.getItem('chatCreatedScenario')

  if (!homeStr && !threatStr && !scenarioStr) {
    return false
  }

  addLogEvent('system', 'Loading scenario from chat...')

  // Load home configuration
  if (homeStr) {
    try {
      const homeData = JSON.parse(homeStr)
      addLogEvent('system', `Home: ${homeData.name || 'Custom Home'}`)

      // Fetch full home data from backend
      try {
        const roomsResponse = await fetch('http://localhost:8000/api/simulation/home/rooms')
        const devicesResponse = await fetch('http://localhost:8000/api/simulation/home/devices')
        const inhabitantsResponse = await fetch('http://localhost:8000/api/simulation/home/inhabitants')

        if (roomsResponse.ok && devicesResponse.ok) {
          const roomsData = await roomsResponse.json()
          const devicesData = await devicesResponse.json()
          const inhabitantsData = inhabitantsResponse.ok ? await inhabitantsResponse.json() : []

          // Group devices by room
          const devicesByRoom: Record<string, typeof devicesData> = {}
          for (const device of devicesData) {
            const roomId = device.room_id || 'unassigned'
            if (!devicesByRoom[roomId]) {
              devicesByRoom[roomId] = []
            }
            devicesByRoom[roomId].push(device)
          }

          // Build room layout with grid positioning
          const roomWidth = 180
          const roomHeight = 130
          const cols = 3
          const startX = 50
          const startY = 50
          const gap = 20

          homeConfig.value = {
            rooms: roomsData.map((room: Record<string, unknown>, index: number) => {
              const col = index % cols
              const row = Math.floor(index / cols)
              const roomDevices = devicesByRoom[room.id as string] || []

              return {
                id: room.id as string,
                name: room.name as string,
                type: room.room_type as string,
                x: startX + col * (roomWidth + gap),
                y: startY + row * (roomHeight + gap),
                width: roomWidth,
                height: roomHeight,
                devices: roomDevices.map((device: Record<string, unknown>, devIndex: number) => ({
                  id: device.id as string,
                  name: device.name as string,
                  type: device.device_type as string,
                  icon: getDeviceIcon(device.device_type as string),
                  x: 20 + (devIndex % 4) * 40,
                  y: 40 + Math.floor(devIndex / 4) * 40,
                  status: 'normal' as const,
                })),
              }
            }),
            inhabitants: inhabitantsData.map((inh: Record<string, unknown>) => ({
              id: inh.id as string,
              name: inh.name as string,
              role: inh.inhabitant_type as string || 'adult',
              icon: getInhabitantIcon(inh.inhabitant_type as string),
              currentRoom: inh.current_room_id as string || undefined,
            })),
          }

          addLogEvent('system', `Home loaded: ${homeConfig.value.rooms.length} rooms, ${totalDevices.value} devices`)
        } else {
          throw new Error('Failed to fetch rooms or devices from backend')
        }
      } catch (e) {
        console.error('Failed to load home from backend:', e)
        // Fallback: create basic home from stored info
        addLogEvent('warning', 'Using basic home configuration')
        loadSampleHome()
      }
    } catch (e) {
      console.error('Failed to parse chat home data:', e)
    }
  }

  // Load threat configuration
  if (threatStr) {
    try {
      const threatData = JSON.parse(threatStr)
      const threatName = threatData.name || threatData.threat_type?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Custom Threat'
      addLogEvent('system', `Threat: ${threatName}`)

      // Build threat scenario from the threat data
      const threatEvents: ThreatEvent[] = []

      // Get target devices from loaded home config
      const getTargetDevices = (): string[] => {
        if (homeConfig.value?.rooms) {
          return homeConfig.value.rooms.flatMap(r => r.devices.slice(0, 2).map(d => d.id))
        }
        return ['dev-1', 'dev-2'] // Fallback device IDs
      }

      // Get severity value from string
      const getSeverityValue = (sev: string): number => {
        switch (sev?.toLowerCase()) {
          case 'critical': return 95
          case 'high': return 75
          case 'medium': return 50
          case 'low': return 25
          default: return 50
        }
      }

      // Check if we have multiple threats in all_threats array
      const allThreats = threatData.all_threats || []

      if (allThreats.length > 0) {
        // Create a threat event for EACH threat in the array
        allThreats.forEach((threat: Record<string, unknown>, index: number) => {
          const singleThreatName = (threat.name as string) ||
            (threat.threat_type as string)?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) ||
            `Threat ${index + 1}`
          const mitreTechniques = (threat.mitre_techniques as string[]) || []
          const indicators = (threat.indicators as Array<{ name?: string }>)?.map(i => i.name || 'Suspicious activity') || ['Suspicious activity detected']

          // Stagger start times so threats don't all happen at once
          const startTimeOffset = index * 60 // 60 seconds apart

          threatEvents.push({
            id: `threat-${index + 1}`,
            type: (threat.category as string) || 'malware',
            name: singleThreatName,
            startTime: 30 + startTimeOffset,
            duration: 60,
            severity: ((threat.severity as string) || 'medium') as 'low' | 'medium' | 'high' | 'critical',
            severityValue: getSeverityValue(threat.severity as string),
            targetDevices: getTargetDevices(),
            description: (threat.description as string) || `${singleThreatName} attack scenario`,
            attackVector: mitreTechniques[0] || 'T1059',
            indicators: indicators.slice(0, 3),
            status: 'pending' as const,
          })
        })

        addLogEvent('system', `Created ${allThreats.length} individual threat events`)
      } else if (threatData.threat_type || threatData.name) {
        // Fallback: single threat (backwards compatibility)
        const mitreTechniques = threatData.mitre_techniques || []
        const indicators = threatData.indicators?.map((i: { name?: string }) => i.name || 'Suspicious activity') || ['Suspicious activity detected']

        threatEvents.push({
          id: `threat-1`,
          type: threatData.category || 'malware',
          name: threatName,
          startTime: 30,
          duration: 60,
          severity: (threatData.severity || 'medium') as 'low' | 'medium' | 'high' | 'critical',
          severityValue: getSeverityValue(threatData.severity),
          targetDevices: getTargetDevices(),
          description: threatData.description || `${threatName} attack scenario`,
          attackVector: mitreTechniques[0] || 'T1059',
          indicators: indicators.slice(0, 3),
          status: 'pending' as const,
        })
      }

      if (threatEvents.length > 0) {
        threatScenario.value = {
          id: `chat-scenario-${Date.now()}`,
          name: threatName,
          simulationDuration: 480,
          events: threatEvents,
        }
        simulationMode.value = 'threat'
        addLogEvent('system', `Loaded ${threatEvents.length} threat(s) - Threat mode enabled`)
      }
    } catch (e) {
      console.error('Failed to parse chat threat data:', e)
    }
  }

  // Log scenario info
  if (scenarioStr) {
    try {
      const scenarioData = JSON.parse(scenarioStr)
      addLogEvent('system', `Scenario ready: ${scenarioData.name || 'Custom Scenario'}`)
      if (scenarioData.ready_to_simulate) {
        addLogEvent('info', 'Click Start to begin simulation')
      }
    } catch (e) {
      console.error('Failed to parse chat scenario data:', e)
    }
  }

  // Clear sessionStorage after loading
  sessionStorage.removeItem('chatCreatedHome')
  sessionStorage.removeItem('chatCreatedThreat')
  sessionStorage.removeItem('chatCreatedScenario')

  return true
}

// Initialize scenario manager and check for pre-loaded scenario from mode store
onMounted(async () => {
  await scenarioManager.initialize()
  preloadedThreatScenarios.value = scenarioManager.getAllThreatScenarios()
  preloadedHomeScenarios.value = scenarioManager.getAllHomeScenarios()

  // First, check if there's a chat-created scenario in sessionStorage
  const loadedFromChat = await loadChatCreatedScenario()
  if (loadedFromChat) {
    return // Skip other loading methods if we loaded from chat
  }

  // Check if there's a scenario that was just executed from the Dashboard
  const executedScenario = modeStore.lastExecutedScenario
  if (executedScenario && executedScenario.results) {
    addLogEvent('system', `Loading scenario: ${executedScenario.scenario_name}`)

    // Load the home configuration from the scenario results
    if (executedScenario.results.home) {
      // Fetch rooms and devices separately from backend
      try {
        // Fetch rooms
        const roomsResponse = await fetch('http://localhost:8000/api/simulation/home/rooms')
        const devicesResponse = await fetch('http://localhost:8000/api/simulation/home/devices')
        const inhabitantsResponse = await fetch('http://localhost:8000/api/simulation/home/inhabitants')

        if (roomsResponse.ok && devicesResponse.ok) {
          const roomsData = await roomsResponse.json()
          const devicesData = await devicesResponse.json()
          const inhabitantsData = inhabitantsResponse.ok ? await inhabitantsResponse.json() : []

          // Group devices by room
          const devicesByRoom: Record<string, typeof devicesData> = {}
          for (const device of devicesData) {
            const roomId = device.room_id || 'unassigned'
            if (!devicesByRoom[roomId]) {
              devicesByRoom[roomId] = []
            }
            devicesByRoom[roomId].push(device)
          }

          // Build room layout with grid positioning
          const roomWidth = 180
          const roomHeight = 130
          const cols = 3
          const startX = 50
          const startY = 50
          const gap = 20

          homeConfig.value = {
            rooms: roomsData.map((room: Record<string, unknown>, index: number) => {
              const col = index % cols
              const row = Math.floor(index / cols)
              const roomDevices = devicesByRoom[room.id as string] || []

              return {
                id: room.id as string,
                name: room.name as string,
                type: room.room_type as string,
                x: startX + col * (roomWidth + gap),
                y: startY + row * (roomHeight + gap),
                width: roomWidth,
                height: roomHeight,
                devices: roomDevices.map((device: Record<string, unknown>, devIndex: number) => ({
                  id: device.id as string,
                  name: device.name as string,
                  type: device.device_type as string,
                  icon: getDeviceIcon(device.device_type as string),
                  x: 20 + (devIndex % 4) * 40,
                  y: 40 + Math.floor(devIndex / 4) * 40,
                  status: 'normal' as const,
                })),
              }
            }),
            inhabitants: inhabitantsData.map((inh: Record<string, unknown>) => ({
              id: inh.id as string,
              name: inh.name as string,
              role: inh.inhabitant_type as string || 'adult',
              icon: getInhabitantIcon(inh.inhabitant_type as string),
              currentRoom: inh.current_room_id as string || undefined,
            })),
          }

          addLogEvent('system', `Home loaded: ${homeConfig.value.rooms.length} rooms, ${totalDevices.value} devices`)
        } else {
          throw new Error('Failed to fetch rooms or devices')
        }
      } catch (e) {
        // If fetch fails, create a basic home from the scenario info
        console.error('Failed to load home from backend:', e)
        addLogEvent('warning', 'Could not fetch full home data, using scenario summary')
        loadSampleHome()
      }
    }

    // Load threat config if present
    if (executedScenario.results.threats) {
      const threatsConfig = executedScenario.results.threats as {
        configured_threats: string[]
        severity: string
        threat_details?: Array<{
          id: string
          name: string
          description: string
          category: string
          severity: string
          detection_difficulty: number
          typical_duration_minutes: [number, number]
          indicators: string[]
          mitre_techniques: string[]
        }>
      }

      if (threatsConfig.threat_details && threatsConfig.threat_details.length > 0) {
        // Build threat scenario from the scenario-specific threat details
        const scenarioThreats: ThreatEvent[] = threatsConfig.threat_details.map((threat, index) => {
          const severityMap: Record<string, 'low' | 'medium' | 'high' | 'critical'> = {
            low: 'low',
            medium: 'medium',
            high: 'high',
            critical: 'critical',
          }
          const severityValueMap: Record<string, number> = {
            low: 25,
            medium: 50,
            high: 75,
            critical: 100,
          }

          // Stagger threat start times
          const startTime = 30 + index * 60

          return {
            id: `threat-${index + 1}`,
            type: threat.category,
            name: threat.name,
            startTime,
            duration: Math.floor((threat.typical_duration_minutes[0] + threat.typical_duration_minutes[1]) / 2),
            severity: severityMap[threat.severity] || 'medium',
            severityValue: severityValueMap[threat.severity] || 50,
            targetDevices: homeConfig.value?.rooms.flatMap(r => r.devices.slice(0, 2).map(d => d.id)) || [],
            description: threat.description,
            attackVector: threat.mitre_techniques[0] || 'Unknown',
            indicators: threat.indicators,
            status: 'pending' as const,
          }
        })

        threatScenario.value = {
          id: `scenario-${executedScenario.scenario_id}`,
          name: `${executedScenario.scenario_name} Threats`,
          simulationDuration: 480,
          events: scenarioThreats,
        }

        addLogEvent('system', `Loaded ${scenarioThreats.length} scenario-specific threats`)
      } else {
        // Fallback to sample threats if no details available
        loadSampleThreats()
      }

      simulationMode.value = 'threat'
      addLogEvent('system', 'Threat scenario configured - switch to Threat mode to simulate attacks')
    }

    // Clear the executed scenario from the store
    modeStore.clearLastExecutedScenario()
  }
})

// Helper functions for icons
function getDeviceIcon(deviceType: string): string {
  const icons: Record<string, string> = {
    smart_light: '💡',
    thermostat: '🌡️',
    smart_lock: '🔒',
    security_camera: '📷',
    motion_sensor: '👁️',
    smoke_detector: '🔥',
    smart_plug: '🔌',
    smart_speaker: '🔊',
    tv: '📺',
    default: '📱',
  }
  return icons[deviceType] || icons.default
}

function getInhabitantIcon(role: string): string {
  const icons: Record<string, string> = {
    adult: '👨',
    child: '👧',
    elderly: '👴',
    default: '👤',
  }
  return icons[role] || icons.default
}

// File input refs
const homeFileInput = ref<HTMLInputElement | null>(null)
const threatFileInput = ref<HTMLInputElement | null>(null)

// ============== COMPUTED ==============

const formattedTime = computed(() => {
  // Convert minutes to total seconds for accurate display
  const totalSeconds = Math.round(currentTime.value * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  // Show HH:MM:SS format for precise tracking
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
})

const formattedTotalTime = computed(() => {
  // Convert minutes to total seconds for accurate display
  const totalSeconds = Math.round(simulationDuration.value * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  // Show HH:MM:SS format for precise tracking
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
})

const progressPercent = computed(() => {
  if (simulationDuration.value === 0) return 0
  return Math.min(100, (currentTime.value / simulationDuration.value) * 100)
})

const totalDevices = computed(() => {
  if (!homeConfig.value) return 0
  return homeConfig.value.rooms.reduce((sum, room) => sum + room.devices.length, 0)
})

// Estimated real-time duration based on speed setting
// Speed 1x = real-time, 2x = 2× faster, etc.
const estimatedRealDuration = computed(() => {
  const simMinutes = simulationDuration.value
  // Real seconds = simulated minutes × 60 / speed
  const realSeconds = (simMinutes * 60) / simulationSpeed.value
  if (realSeconds < 60) return `${Math.round(realSeconds)} sec`
  if (realSeconds < 3600) return `${Math.round(realSeconds / 60)} min`
  const hours = Math.floor(realSeconds / 3600)
  const mins = Math.round((realSeconds % 3600) / 60)
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
})

// Format duration for display (converts minutes to readable format)
// Handles fractional minutes (e.g., 1.5 min = 90 seconds = "1m 30s")
const formattedDurationLabel = computed(() => {
  const mins = simulationDuration.value
  const totalSeconds = Math.round(mins * 60)

  // Less than 1 minute: show seconds only
  if (totalSeconds < 60) return `${totalSeconds}s`

  // Less than 1 hour: show minutes and seconds
  if (mins < 60) {
    const wholeMinutes = Math.floor(mins)
    const remainSeconds = totalSeconds % 60
    if (remainSeconds > 0) {
      return `${wholeMinutes}m ${remainSeconds}s`
    }
    return `${wholeMinutes} min`
  }

  // Less than 1 hour: show hours and minutes
  if (mins < 1440) {
    const hours = Math.floor(mins / 60)
    const remainMins = Math.round(mins % 60)
    return remainMins > 0 ? `${hours}h ${remainMins}m` : `${hours} hour${hours > 1 ? 's' : ''}`
  }

  // 1 day or more: show days and hours
  const days = Math.floor(mins / 1440)
  const remainHours = Math.floor((mins % 1440) / 60)
  return remainHours > 0 ? `${days}d ${remainHours}h` : `${days} day${days > 1 ? 's' : ''}`
})

// ============== METHODS ==============

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

// File loading
function triggerHomeLoad() {
  homeFileInput.value?.click()
}

function triggerThreatLoad() {
  threatFileInput.value?.click()
}

function handleHomeFileLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const config = JSON.parse(content)

      if (!config.rooms || !Array.isArray(config.rooms)) {
        alert('Invalid home configuration file')
        return
      }

      // Initialize device status
      config.rooms.forEach((room: Room) => {
        room.devices.forEach((device: Device) => {
          device.status = 'normal'
        })
      })

      homeConfig.value = config
      addLogEvent('system', `Loaded home configuration: ${config.rooms.length} rooms, ${totalDevices.value} devices`)
    } catch (err) {
      console.error('Failed to parse home config:', err)
      alert('Invalid JSON format')
    }
  }
  reader.readAsText(file)
  input.value = ''
}

function handleThreatFileLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const scenario = JSON.parse(content)

      if (!scenario.events || !Array.isArray(scenario.events)) {
        alert('Invalid threat scenario file')
        return
      }

      // Initialize event status
      scenario.events.forEach((event: ThreatEvent) => {
        event.status = 'pending'
      })

      threatScenario.value = {
        ...scenario,
        id: scenario.id || generateId(),
        name: scenario.name || 'Imported Scenario',
        simulationDuration: scenario.simulationDuration || scenario.estimatedDuration || 480,
      }

      simulationDuration.value = threatScenario.value?.simulationDuration ?? 480
      addLogEvent('system', `Loaded threat scenario: ${scenario.events.length} events`)
    } catch (err) {
      console.error('Failed to parse threat scenario:', err)
      alert('Invalid JSON format')
    }
  }
  reader.readAsText(file)
  input.value = ''
}

// Sample data loaders
function loadSampleHome() {
  homeConfig.value = {
    rooms: [
      {
        id: 'room-1',
        name: 'Living Room',
        type: 'living_room',
        x: 50,
        y: 50,
        width: 200,
        height: 150,
        devices: [
          { id: 'dev-1', name: 'Smart Light', type: 'smart_light', icon: '💡', x: 30, y: 30, status: 'normal' },
          { id: 'dev-2', name: 'Thermostat', type: 'thermostat', icon: '🌡️', x: 80, y: 30, status: 'normal' },
          { id: 'dev-3', name: 'Smart TV', type: 'tv', icon: '📺', x: 130, y: 30, status: 'normal' },
        ],
      },
      {
        id: 'room-2',
        name: 'Bedroom',
        type: 'bedroom',
        x: 270,
        y: 50,
        width: 160,
        height: 120,
        devices: [
          { id: 'dev-4', name: 'Smart Light', type: 'smart_light', icon: '💡', x: 30, y: 30, status: 'normal' },
          { id: 'dev-5', name: 'Smart Speaker', type: 'speaker', icon: '🔊', x: 80, y: 30, status: 'normal' },
        ],
      },
      {
        id: 'room-3',
        name: 'Kitchen',
        type: 'kitchen',
        x: 50,
        y: 220,
        width: 180,
        height: 130,
        devices: [
          { id: 'dev-6', name: 'Smart Light', type: 'smart_light', icon: '💡', x: 30, y: 30, status: 'normal' },
          { id: 'dev-7', name: 'Smoke Detector', type: 'smoke_detector', icon: '🔥', x: 80, y: 30, status: 'normal' },
          { id: 'dev-8', name: 'Smart Plug', type: 'smart_plug', icon: '🔌', x: 130, y: 30, status: 'normal' },
        ],
      },
      {
        id: 'room-4',
        name: 'Front Door',
        type: 'hallway',
        x: 270,
        y: 190,
        width: 160,
        height: 100,
        devices: [
          { id: 'dev-9', name: 'Smart Lock', type: 'door_lock', icon: '🔒', x: 30, y: 30, status: 'normal' },
          { id: 'dev-10', name: 'Camera', type: 'camera', icon: '📷', x: 80, y: 30, status: 'normal' },
          { id: 'dev-11', name: 'Motion Sensor', type: 'motion_sensor', icon: '👁️', x: 130, y: 30, status: 'normal' },
        ],
      },
    ],
    inhabitants: [
      { id: 'inh-1', name: 'John', role: 'adult', icon: '👨', currentRoom: 'room-1' },
      { id: 'inh-2', name: 'Jane', role: 'adult', icon: '👩', currentRoom: 'room-2' },
    ],
  }
  addLogEvent('system', 'Loaded sample home configuration')
}

function loadSampleThreats() {
  threatScenario.value = {
    id: 'sample-scenario',
    name: 'Sample Attack Scenario',
    simulationDuration: 60,
    events: [
      {
        id: 'threat-1',
        type: 'reconnaissance',
        name: 'Network Scanning',
        startTime: 5,
        duration: 5,
        severity: 'low',
        severityValue: 25,
        targetDevices: ['dev-10'],
        description: 'Attacker scans network to identify IoT devices',
        attackVector: 'T1595',
        indicators: ['Port scanning activity'],
        status: 'pending',
      },
      {
        id: 'threat-2',
        type: 'credential_attack',
        name: 'Default Credential Attack',
        startTime: 15,
        duration: 8,
        severity: 'medium',
        severityValue: 50,
        targetDevices: ['dev-10', 'dev-9'],
        description: 'Attempting to login with default credentials',
        attackVector: 'T1078.001',
        indicators: ['Multiple login attempts', 'Failed authentications'],
        status: 'pending',
      },
      {
        id: 'threat-3',
        type: 'man_in_the_middle',
        name: 'MITM Attack on Smart Hub',
        startTime: 30,
        duration: 10,
        severity: 'high',
        severityValue: 75,
        targetDevices: ['dev-2', 'dev-1'],
        description: 'Intercepting communication between devices',
        attackVector: 'T1557',
        indicators: ['ARP spoofing', 'Unusual network traffic'],
        status: 'pending',
      },
      {
        id: 'threat-4',
        type: 'data_exfiltration',
        name: 'Camera Feed Exfiltration',
        startTime: 45,
        duration: 12,
        severity: 'critical',
        severityValue: 95,
        targetDevices: ['dev-10'],
        description: 'Stealing camera footage to external server',
        attackVector: 'T1041',
        indicators: ['Large outbound data transfer', 'Unusual upload activity'],
        status: 'pending',
      },
    ],
  }
  simulationDuration.value = 60
  addLogEvent('system', 'Loaded sample threat scenario')
}

// Load preloaded threat scenario
function loadPreloadedThreat(scenario: PreloadedThreatScenario) {
  // Convert preloaded scenario to simulation format
  const events: ThreatEvent[] = scenario.events.map(e => ({
    id: e.id,
    type: e.type,
    name: e.name,
    startTime: e.startTime,
    duration: e.duration,
    severity: e.severity,
    severityValue: e.severityValue,
    targetDevices: e.targetDevices,
    description: e.description,
    attackVector: e.attackVector,
    indicators: e.indicators,
    status: 'pending' as const,
  }))

  threatScenario.value = {
    id: scenario.id,
    name: scenario.name,
    events,
    simulationDuration: scenario.simulationDuration,
  }
  simulationDuration.value = scenario.simulationDuration
  showThreatPicker.value = false
  addLogEvent('system', `Loaded preloaded threat scenario: ${scenario.name}`)
}

// Load preloaded home scenario
function loadPreloadedHome(scenario: PreloadedHomeScenario) {
  // Convert preloaded home to simulation format
  const rooms: Room[] = scenario.rooms.map(r => ({
    id: r.id,
    name: r.name,
    type: r.type,
    x: r.x,
    y: r.y,
    width: r.width,
    height: r.height,
    devices: r.devices.map(d => ({
      id: d.id,
      name: d.name,
      type: d.type,
      icon: d.icon,
      x: d.x,
      y: d.y,
      status: 'normal' as const,
    })),
  }))

  const inhabitants: Inhabitant[] = scenario.inhabitants.map(i => ({
    id: i.id,
    name: i.name,
    role: i.role,
    icon: i.icon,
    currentRoom: undefined,
  }))

  homeConfig.value = {
    rooms,
    inhabitants,
    createdAt: scenario.createdAt,
  }
  showHomePicker.value = false
  addLogEvent('system', `Loaded preloaded home: ${scenario.name}`)
}

// Set simulation mode
function setSimulationMode(mode: SimulationMode) {
  simulationMode.value = mode
  // If switching to threat mode and no scenario loaded, clear benign mode
  // If switching to benign mode, that's fine even with threats loaded
}

// Simulation controls
async function startSimulation() {
  if (!homeConfig.value) {
    alert('Please load a home configuration first')
    return
  }

  // In threat mode, require a threat scenario
  if (simulationMode.value === 'threat' && !threatScenario.value) {
    alert('Please load a threat scenario first, or switch to Benign Mode')
    return
  }

  if (simulationState.value === 'idle' || simulationState.value === 'completed') {
    // Reset simulation
    currentTime.value = 0
    resetDeviceStatus()
    resetThreatStatus()
    eventLog.value = []
    backendEvents.value = []
    lastEventCount.value = 0
    backendCompletionLogged.value = false
    simulationStartTime.value = null
    stats.value = {
      totalEvents: 0,
      detectedThreats: 0,
      blockedThreats: 0,
      compromisedDevices: 0,
      alertsGenerated: 0,
    }

    // Try to start backend simulation
    if (useBackendSimulation.value) {
      try {
        // Check if backend is available
        const isAvailable = await simulationApi.checkAvailability()
        if (isAvailable) {
          addLogEvent('system', 'Connecting to backend SimulationEngine...')

          // Stop any previous simulation before starting a new one
          try {
            await simulationApi.stop()
            addLogEvent('system', 'Stopped previous simulation')
            // Brief delay to allow backend to clean up
            await new Promise(resolve => setTimeout(resolve, 500))
          } catch {
            // Ignore - no simulation was running
          }

          // Create home in backend
          const backendConfig = convertHomeConfigToBackend(homeConfig.value, 'Simulation Home')
          await simulationApi.createCustomHome(backendConfig)

          // Start backend simulation
          const durationHours = simulationDuration.value / 60

          // Prepare threats array if in threat mode
          const threatsToSend = simulationMode.value === 'threat' && threatScenario.value
            ? threatScenario.value.events.map(t => ({
                id: t.id,
                type: t.type,
                name: t.name,
                startTime: t.startTime,
                duration: t.duration,
                severity: t.severity,
                severityValue: t.severityValue,
                targetDevices: t.targetDevices,
                description: t.description,
                attackVector: t.attackVector,
              }))
            : undefined

          // Calculate time compression based on speed setting
          // Speed 1x = real-time (compression = 1)
          // Speed 2x = 2× faster (compression = 2)
          // Speed 10x = 10× faster (compression = 10)
          const timeCompression = simulationSpeed.value

          const status = await simulationApi.start({
            duration_hours: durationHours,
            time_compression: timeCompression,
            enable_threats: simulationMode.value === 'threat',
            collect_all_events: true,
            threats: threatsToSend,
          })

          backendSimulationId.value = status.id
          // Store simulation start time for timestamp calculations
          simulationStartTime.value = status.simulation_time || new Date().toISOString()
          addLogEvent('system', `Backend simulation started (ID: ${status.id.substring(0, 8)}...)`)
        } else {
          addLogEvent('system', 'Backend unavailable - using frontend simulation only')
        }
      } catch (error) {
        console.error('Backend simulation error:', error)
        let errorMessage = 'Unknown error'
        if (error instanceof Error) {
          errorMessage = error.message
        } else if (typeof error === 'object' && error !== null) {
          errorMessage = JSON.stringify(error)
        } else if (typeof error === 'string') {
          errorMessage = error
        }
        addLogEvent('warning', `Backend unavailable: ${errorMessage}`)
        backendSimulationId.value = null
      }
    }

    if (simulationMode.value === 'benign') {
      addLogEvent('system', 'Benign simulation started - Normal home activity')
    } else {
      addLogEvent('system', 'Threat simulation started')
    }
  }

  simulationState.value = 'running'
  startSimulationLoop()
}

async function pauseSimulation() {
  simulationState.value = 'paused'
  stopSimulationLoop()

  // Pause backend simulation
  if (backendSimulationId.value) {
    try {
      await simulationApi.pause()
      addLogEvent('system', 'Backend simulation paused')
    } catch (error) {
      console.error('Failed to pause backend simulation:', error)
    }
  }

  addLogEvent('system', 'Simulation paused')
}

async function resumeSimulation() {
  simulationState.value = 'running'
  startSimulationLoop()

  // Resume backend simulation
  if (backendSimulationId.value) {
    try {
      await simulationApi.resume()
      addLogEvent('system', 'Backend simulation resumed')
    } catch (error) {
      console.error('Failed to resume backend simulation:', error)
    }
  }

  addLogEvent('system', 'Simulation resumed')
}

async function stopSimulation() {
  simulationState.value = 'idle'
  stopSimulationLoop()

  // Stop backend simulation
  if (backendSimulationId.value) {
    try {
      await simulationApi.stop()
      addLogEvent('system', 'Backend simulation stopped')
    } catch (error) {
      console.error('Failed to stop backend simulation:', error)
    }
    backendSimulationId.value = null
  }

  currentTime.value = 0
  resetDeviceStatus()
  resetThreatStatus()
  addLogEvent('system', 'Simulation stopped')
}

function resetDeviceStatus() {
  if (!homeConfig.value) return
  homeConfig.value.rooms.forEach(room => {
    room.devices.forEach(device => {
      device.status = 'normal'
    })
  })
}

function resetThreatStatus() {
  if (!threatScenario.value) return
  threatScenario.value.events.forEach(event => {
    event.status = 'pending'
  })
}

function startSimulationLoop() {
  if (simulationInterval) return

  // Update every second
  // At 1x speed: 1 simulated minute = 60 real seconds, so advance 1/60 min per second
  // At 10x speed: 1 simulated minute = 6 real seconds, so advance 10/60 min per second
  // Formula: advance (simulationSpeed / 60) minutes per real second
  simulationInterval = setInterval(() => {
    if (simulationState.value !== 'running') return

    // Advance time based on speed multiplier
    // simulationSpeed=1 means real-time (1 min takes 60 seconds)
    // simulationSpeed=10 means 10x faster (1 min takes 6 seconds)
    currentTime.value += simulationSpeed.value / 60

    // NOTE: Local threat processing removed - all threat events now come from backend
    // Threats are processed by the Simulator's ThreatInjector and returned via /api/simulation/events

    // Check for simulation completion
    if (currentTime.value >= simulationDuration.value) {
      completeSimulation()
    }
  }, 1000)

  // Start backend polling if backend simulation is active
  if (backendSimulationId.value && !backendPollInterval) {
    startBackendPolling()
  }
}

function startBackendPolling() {
  if (backendPollInterval) return

  backendPollInterval = setInterval(async () => {
    if (simulationState.value !== 'running' || !backendSimulationId.value) return

    try {
      // Poll status
      const status = await simulationApi.getStatus()

      // Sync frontend time with backend simulation time using progress
      // This ensures the frontend timer matches the backend's actual simulation progress
      if (status.progress_percent > 0 && status.state === 'running') {
        const syncedTime = Math.floor((status.progress_percent / 100) * simulationDuration.value)
        if (syncedTime > currentTime.value) {
          currentTime.value = syncedTime
        }
      }

      // Update stats from backend
      if (status.total_events > lastEventCount.value) {
        // Fetch new events - increase limit to catch up with fast-running backend
        const events = await simulationApi.getEvents({
          limit: 200, // Larger batch to keep up with 1440x compression
          offset: lastEventCount.value,
        })

        // Process new events
        processBackendEvents(events)
        // Only increment by actual events fetched, not total - ensures we don't skip events
        lastEventCount.value += events.length
      }

      // Check backend simulation state - only log completion once
      if (status.state === 'completed' && !backendCompletionLogged.value) {
        backendCompletionLogged.value = true

        // Fetch ALL remaining events before completing (not just 50)
        if (status.total_events > lastEventCount.value) {
          const remainingCount = status.total_events - lastEventCount.value
          const allRemainingEvents = await simulationApi.getEvents({
            limit: Math.min(remainingCount + 100, 5000), // Fetch all remaining with some buffer
            offset: lastEventCount.value,
          })
          processBackendEvents(allRemainingEvents)
          lastEventCount.value = status.total_events
        }

        // Sync final time to full duration
        currentTime.value = simulationDuration.value
        addLogEvent('system', `Backend simulation completed: ${status.total_events} events generated`)
        // Auto-complete the frontend simulation
        completeSimulation()
      } else if (status.state === 'error' && !backendCompletionLogged.value) {
        backendCompletionLogged.value = true
        addLogEvent('warning', 'Backend simulation encountered an error')
      }
    } catch (error) {
      console.error('Backend polling error:', error)
    }
  }, 2000) // Poll every 2 seconds
}

function processBackendEvents(events: BackendSimEvent[]) {
  for (const event of events) {
    backendEvents.value.push(event)

    // Calculate event timestamp in minutes from simulation start
    // Backend timestamp is ISO string, we need to convert to minutes from start
    let eventTimeMinutes = currentTime.value
    if (event.timestamp && simulationStartTime.value) {
      const eventDate = new Date(event.timestamp)
      const startDate = new Date(simulationStartTime.value)
      const diffMs = eventDate.getTime() - startDate.getTime()
      eventTimeMinutes = Math.floor(diffMs / (1000 * 60))
    }

    // Convert backend event to frontend log format
    const eventType = mapBackendEventType(event.event_type)
    const message = formatBackendEventMessage(event)

    addLogEvent(eventType, message, event.source_id, undefined, eventTimeMinutes)

    // Update stats based on event type
    stats.value.totalEvents++
    if (event.is_anomaly) {
      stats.value.alertsGenerated++
    }

    // Handle threat events from backend
    if (event.event_type === 'threat_injected') {
      // Update threat timeline if we have a matching threat scenario
      // For threat events, source_id IS the threat_id (set in engine.py)
      const threatId = event.source_id
      if (threatScenario.value) {
        const threatEvent = threatScenario.value.events.find(t => t.id === threatId)
        if (threatEvent) {
          threatEvent.status = 'active'
          stats.value.detectedThreats++
          // Mark targeted devices as warning
          threatEvent.targetDevices.forEach(deviceId => {
            setDeviceStatus(deviceId, 'warning')
          })
        }
      }
    } else if (event.event_type === 'threat_detected') {
      const threatId = event.source_id
      if (threatScenario.value) {
        const threatEvent = threatScenario.value.events.find(t => t.id === threatId)
        if (threatEvent) {
          threatEvent.status = 'detected'
          stats.value.blockedThreats++
        }
      }
    }
  }
}

function mapBackendEventType(eventType: string): SimulationEvent['type'] {
  switch (eventType) {
    case 'device_data_generated':
      return 'info'
    case 'device_state_change':
      return 'info'
    case 'security_alert':
      return 'warning'
    case 'network_anomaly':
      return 'attack'
    case 'inhabitant_action':
      return 'info'
    case 'system_event':
      return 'system'
    case 'threat_injected':
      return 'attack'
    case 'threat_detected':
      return 'detection'
    default:
      return 'info'
  }
}

function formatBackendEventMessage(event: BackendSimEvent): string {
  const deviceName = event.data?.device_name || event.source_id
  const deviceType = event.data?.device_type || 'device'

  switch (event.event_type) {
    case 'device_data_generated':
      return `[${deviceType}] ${deviceName}: telemetry data recorded`
    case 'device_state_change':
      return `[${deviceType}] ${deviceName}: state changed`
    case 'security_alert':
      return `Security alert from ${deviceName}`
    case 'network_anomaly':
      return `Network anomaly detected: ${event.data?.description || 'unknown'}`
    case 'inhabitant_action':
      return `Inhabitant activity: ${event.data?.action || 'action'}`
    case 'system_event':
      return `System: ${event.data?.event || event.data?.message || 'event'}`
    case 'threat_injected':
      return `Attack started: ${event.data?.name || event.data?.threat_type || 'unknown threat'}`
    case 'threat_detected':
      return `Threat detected: ${event.data?.name || event.data?.threat_type || 'unknown threat'}`
    default:
      return `${event.event_type}: ${deviceName}`
  }
}

function stopSimulationLoop() {
  if (simulationInterval) {
    clearInterval(simulationInterval)
    simulationInterval = null
  }
  if (backendPollInterval) {
    clearInterval(backendPollInterval)
    backendPollInterval = null
  }
}

function processThreatEvents() {
  if (!threatScenario.value || !homeConfig.value) return

  threatScenario.value.events.forEach(event => {
    const eventEnd = event.startTime + event.duration

    // Start event
    if (event.status === 'pending' && currentTime.value >= event.startTime) {
      event.status = 'active'
      stats.value.totalEvents++
      addLogEvent('attack', `Attack started: ${event.name}`, undefined, event.id)

      // Mark targeted devices as warning
      event.targetDevices.forEach(deviceId => {
        setDeviceStatus(deviceId, 'warning')
      })
    }

    // Process active event
    if (event.status === 'active') {
      // Simulate detection chance (higher severity = higher detection chance)
      const detectionChance = (event.severityValue / 100) * 0.02 // 2% max per tick for critical
      if (Math.random() < detectionChance) {
        event.status = 'detected'
        stats.value.detectedThreats++
        stats.value.alertsGenerated++
        addLogEvent('detection', `Threat detected: ${event.name}`, undefined, event.id)

        // 50% chance to block after detection
        if (Math.random() < 0.5) {
          event.status = 'blocked'
          stats.value.blockedThreats++
          addLogEvent('info', `Threat blocked: ${event.name}`, undefined, event.id)
          event.targetDevices.forEach(deviceId => {
            setDeviceStatus(deviceId, 'normal')
          })
        }
      }

      // Event completes naturally
      if (currentTime.value >= eventEnd && event.status === 'active') {
        event.status = 'completed'
        addLogEvent('warning', `Attack completed: ${event.name}`, undefined, event.id)

        // Mark devices as compromised
        event.targetDevices.forEach(deviceId => {
          if (getDeviceStatus(deviceId) !== 'normal') {
            setDeviceStatus(deviceId, 'compromised')
            stats.value.compromisedDevices++
          }
        })
      }
    }
  })
}

function setDeviceStatus(deviceId: string, status: Device['status']) {
  if (!homeConfig.value) return
  homeConfig.value.rooms.forEach(room => {
    const device = room.devices.find(d => d.id === deviceId)
    if (device) {
      device.status = status
    }
  })
}

function getDeviceStatus(deviceId: string): Device['status'] | null {
  if (!homeConfig.value) return null
  for (const room of homeConfig.value.rooms) {
    const device = room.devices.find(d => d.id === deviceId)
    if (device) return device.status
  }
  return null
}

function completeSimulation() {
  simulationState.value = 'completed'
  stopSimulationLoop()
  addLogEvent('system', 'Simulation completed')
}

function addLogEvent(
  type: SimulationEvent['type'],
  message: string,
  deviceId?: string,
  threatId?: string,
  timestamp?: number
) {
  const event: SimulationEvent = {
    id: generateId(),
    timestamp: timestamp ?? currentTime.value,
    type,
    message,
    deviceId,
    threatId,
  }

  eventLog.value.unshift(event)

  // Trim log if too long
  if (eventLog.value.length > maxLogEvents) {
    eventLog.value = eventLog.value.slice(0, maxLogEvents)
  }
}

function setSpeed(speed: number) {
  simulationSpeed.value = speed
  showCustomSpeedInput.value = false
}

function applyCustomSpeed() {
  if (customSpeedValue.value >= 1) {
    simulationSpeed.value = customSpeedValue.value
    showCustomSpeedInput.value = false
  }
}

function openCustomDurationDialog() {
  // Initialize with current duration converted to seconds
  // Handle case where simulationDuration might be NaN or invalid
  const currentMins = Number(simulationDuration.value)
  customDurationSeconds.value = !isNaN(currentMins) && currentMins > 0 ? currentMins * 60 : 3600
  showCustomDurationDialog.value = true
}

function applyCustomDuration() {
  if (customDurationSeconds.value >= 60) { // Minimum 1 minute
    // Store exact seconds as fractional minutes for precision
    // e.g., 90 seconds = 1.5 minutes
    simulationDuration.value = customDurationSeconds.value / 60
    showCustomDurationDialog.value = false
  }
}

function cancelCustomDuration() {
  showCustomDurationDialog.value = false
}

function getDeviceStatusColor(status: Device['status']): string {
  switch (status) {
    case 'normal': return 'var(--color-success)'
    case 'warning': return 'var(--color-warning)'
    case 'compromised': return 'var(--color-danger)'
    case 'offline': return 'var(--text-muted)'
    default: return 'var(--text-secondary)'
  }
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'low': return '#22c55e'
    case 'medium': return '#eab308'
    case 'high': return '#f97316'
    case 'critical': return '#ef4444'
    default: return '#6b7280'
  }
}

function getEventTypeIcon(type: SimulationEvent['type']): string {
  switch (type) {
    case 'info': return 'i'
    case 'warning': return '!'
    case 'attack': return '⚠'
    case 'detection': return '🛡'
    case 'system': return '⚙'
    default: return '•'
  }
}

function formatLogTime(minutes: number): string {
  // Convert minutes to total seconds for proper HH:MM:SS display
  const totalSeconds = Math.round(minutes * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const mins = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function exportResults() {
  const results = {
    simulationId: generateId(),
    completedAt: new Date().toISOString(),
    duration: currentTime.value,
    homeConfig: homeConfig.value,
    threatScenario: threatScenario.value,
    statistics: stats.value,
    eventLog: eventLog.value,
  }

  const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `simulation-results-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// Save as Experiment
function openSaveModal() {
  // Pre-fill with default name
  const timestamp = new Date().toLocaleString()
  const mode = simulationMode.value === 'threat' ? 'Threat' : 'Benign'
  saveForm.value = {
    name: `${mode} Simulation - ${timestamp}`,
    description: '',
    tags: simulationMode.value,
  }
  saveError.value = ''
  saveSuccess.value = false
  showSaveModal.value = true
}

function closeSaveModal() {
  showSaveModal.value = false
  saveError.value = ''
  saveSuccess.value = false
}

async function saveAsExperiment() {
  if (!saveForm.value.name.trim()) {
    saveError.value = 'Name is required'
    return
  }

  isSaving.value = true
  saveError.value = ''

  try {
    const response = await fetch('/api/experiments/from-simulation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: saveForm.value.name.trim(),
        description: saveForm.value.description.trim() || null,
        tags: saveForm.value.tags.split(',').map(t => t.trim()).filter(Boolean),
        simulation_id: generateId(),
        completed_at: new Date().toISOString(),
        duration_minutes: currentTime.value,
        simulation_mode: simulationMode.value,
        home_config: homeConfig.value,
        threat_scenario: threatScenario.value,
        statistics: stats.value,
        event_log: eventLog.value,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to save experiment')
    }

    saveSuccess.value = true
    addLogEvent('system', `Simulation saved as experiment: ${saveForm.value.name}`)

    // Close modal after brief delay
    setTimeout(() => {
      closeSaveModal()
    }, 1500)
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to save experiment'
    saveError.value = message
  } finally {
    isSaving.value = false
  }
}

// Cleanup on unmount
onUnmounted(() => {
  stopSimulationLoop()
})

// Watch for speed changes during running simulation
watch(simulationSpeed, () => {
  if (simulationState.value === 'running') {
    addLogEvent('system', `Simulation speed changed to ${simulationSpeed.value}x`)
  }
})
</script>

<template>
  <div class="simulation-view">
    <!-- Header -->
    <header class="simulation-header">
      <div class="header-left">
        <h2>Simulation</h2>
        <span class="simulation-status" :class="simulationState">
          {{ simulationState === 'idle' ? 'Ready' : simulationState }}
        </span>
      </div>

      <div class="header-center">
        <!-- Time display -->
        <div class="time-display">
          <span class="current-time">{{ formattedTime }}</span>
          <span class="time-separator">/</span>
          <span class="total-time">{{ formattedTotalTime }}</span>
        </div>

        <!-- Progress bar -->
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>

          <!-- Threat markers on timeline -->
          <div
            v-for="event in threatScenario?.events || []"
            :key="event.id"
            class="threat-marker"
            :class="event.status"
            :style="{ left: `${(event.startTime / simulationDuration) * 100}%` }"
            :title="`${event.name} @ ${formatLogTime(event.startTime)}`"
          >
            <div class="marker-dot" :style="{ backgroundColor: getSeverityColor(event.severity) }"></div>
          </div>
        </div>
      </div>

      <div class="header-right">
        <!-- Mode Toggle -->
        <div class="mode-toggle">
          <button
            class="mode-btn"
            :class="{ active: simulationMode === 'benign' }"
            @click="setSimulationMode('benign')"
            :disabled="simulationState === 'running'"
            title="Run simulation without attacks"
          >
            Benign
          </button>
          <button
            class="mode-btn"
            :class="{ active: simulationMode === 'threat' }"
            @click="setSimulationMode('threat')"
            :disabled="simulationState === 'running'"
            title="Run simulation with attack scenarios"
          >
            Threat
          </button>
        </div>

        <!-- Duration control -->
        <div class="duration-control">
          <label class="duration-label" for="simulation-duration">Duration:</label>
          <select
            id="simulation-duration"
            v-model="simulationDuration"
            class="duration-select"
            :disabled="simulationState === 'running'"
            aria-label="Simulation duration"
            @change="(e) => { if ((e.target as HTMLSelectElement).value === 'custom') openCustomDurationDialog() }"
          >
            <option :value="1">1 min</option>
            <option :value="5">5 min</option>
            <option :value="15">15 min</option>
            <option :value="30">30 min</option>
            <option :value="60">1 hour</option>
            <option :value="120">2 hours</option>
            <option :value="240">4 hours</option>
            <option :value="480">8 hours</option>
            <option :value="720">12 hours</option>
            <option :value="1440">24 hours</option>
            <option :value="2880">48 hours</option>
            <option :value="10080">7 days</option>
            <option value="custom">Custom...</option>
          </select>
          <span v-if="![1, 5, 15, 30, 60, 120, 240, 480, 720, 1440, 2880, 10080].includes(simulationDuration)" class="custom-duration-badge">
            {{ formattedDurationLabel }}
          </span>
        </div>

        <!-- Speed control -->
        <div class="speed-control">
          <button
            v-for="speed in [1, 2, 5, 10]"
            :key="speed"
            class="speed-btn"
            :class="{ active: simulationSpeed === speed && !showCustomSpeedInput }"
            :disabled="simulationState === 'running'"
            @click="setSpeed(speed)"
          >
            {{ speed }}x
          </button>
          <button
            class="speed-btn custom-speed-btn"
            :class="{ active: ![1, 2, 5, 10].includes(simulationSpeed) || showCustomSpeedInput }"
            :disabled="simulationState === 'running'"
            @click="showCustomSpeedInput = !showCustomSpeedInput"
          >
            {{ ![1, 2, 5, 10].includes(simulationSpeed) ? simulationSpeed + 'x' : '+' }}
          </button>
          <div v-if="showCustomSpeedInput" class="custom-speed-input">
            <input
              type="number"
              v-model.number="customSpeedValue"
              min="1"
              max="10000"
              placeholder="Speed"
              @keyup.enter="applyCustomSpeed"
            />
            <button class="apply-btn" @click="applyCustomSpeed">OK</button>
          </div>
        </div>

        <!-- Estimated duration display -->
        <span class="duration-estimate" :title="'Estimated real-time duration'">
          {{ estimatedRealDuration }}
        </span>

        <!-- Playback controls -->
        <div class="playback-controls">
          <button
            v-if="simulationState === 'idle' || simulationState === 'completed'"
            class="btn btn-primary"
            @click="startSimulation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Start
          </button>

          <button
            v-if="simulationState === 'running'"
            class="btn btn-secondary"
            @click="pauseSimulation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16"></rect>
              <rect x="14" y="4" width="4" height="16"></rect>
            </svg>
            Pause
          </button>

          <button
            v-if="simulationState === 'paused'"
            class="btn btn-primary"
            @click="resumeSimulation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Resume
          </button>

          <button
            v-if="simulationState !== 'idle'"
            class="btn btn-ghost"
            @click="stopSimulation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="4" y="4" width="16" height="16"></rect>
            </svg>
            Stop
          </button>
        </div>
      </div>
    </header>

    <div class="simulation-content">
      <!-- Left Panel - Home Visualization -->
      <section class="panel home-panel">
        <div class="panel-header">
          <h3>Home Environment</h3>
          <div class="panel-actions">
            <button class="btn btn-ghost btn-sm" @click="loadSampleHome">Sample</button>
            <button
              v-if="preloadedHomeScenarios.length > 0"
              class="btn btn-ghost btn-sm"
              @click="showHomePicker = !showHomePicker"
            >
              Preloaded
            </button>
            <button class="btn btn-ghost btn-sm" @click="triggerHomeLoad">Load</button>
            <input
              ref="homeFileInput"
              type="file"
              accept=".json"
              style="display: none"
              @change="handleHomeFileLoad"
              aria-label="Load home configuration file"
              aria-hidden="true"
            />
          </div>
        </div>

        <!-- Preloaded Home Picker -->
        <div v-if="showHomePicker" class="scenario-picker">
          <div class="picker-header">
            <h4>Select Preloaded Home</h4>
            <button class="btn btn-ghost btn-icon btn-sm" @click="showHomePicker = false">×</button>
          </div>
          <div class="picker-list">
            <button
              v-for="scenario in preloadedHomeScenarios"
              :key="scenario.id"
              class="picker-item"
              @click="loadPreloadedHome(scenario)"
            >
              <span class="picker-icon">🏠</span>
              <div class="picker-info">
                <span class="picker-name">{{ scenario.name }}</span>
                <span class="picker-desc">{{ scenario.description }}</span>
              </div>
            </button>
          </div>
        </div>

        <div class="panel-content">
          <div v-if="!homeConfig" class="empty-state">
            <div class="empty-icon">🏠</div>
            <p>No home configuration loaded</p>
            <button class="btn btn-primary" @click="loadSampleHome">Load Sample Home</button>
          </div>

          <div v-else class="home-visualization">
            <div
              v-for="room in homeConfig.rooms"
              :key="room.id"
              class="room"
              :style="{
                left: `${room.x}px`,
                top: `${room.y}px`,
                width: `${room.width}px`,
                height: `${room.height}px`,
              }"
            >
              <div class="room-header">{{ room.name }}</div>
              <div class="room-devices">
                <div
                  v-for="device in room.devices"
                  :key="device.id"
                  class="device"
                  :class="device.status"
                  :title="`${device.name} (${device.status})`"
                >
                  <span class="device-icon">{{ device.icon }}</span>
                  <div class="device-indicator" :style="{ backgroundColor: getDeviceStatusColor(device.status) }"></div>
                </div>
              </div>
            </div>

            <!-- Inhabitants -->
            <div
              v-for="inhabitant in homeConfig.inhabitants"
              :key="inhabitant.id"
              class="inhabitant"
              :title="inhabitant.name"
            >
              {{ inhabitant.icon }}
            </div>
          </div>
        </div>

        <!-- Device Legend -->
        <div v-if="homeConfig" class="device-legend">
          <div class="legend-item">
            <span class="legend-dot normal"></span> Normal
          </div>
          <div class="legend-item">
            <span class="legend-dot warning"></span> Under Attack
          </div>
          <div class="legend-item">
            <span class="legend-dot compromised"></span> Compromised
          </div>
        </div>
      </section>

      <!-- Center Panel - Threat Timeline -->
      <section class="panel threat-panel">
        <div class="panel-header">
          <h3>Threat Timeline</h3>
          <div class="panel-actions">
            <button class="btn btn-ghost btn-sm" @click="loadSampleThreats">Sample</button>
            <button
              v-if="preloadedThreatScenarios.length > 0"
              class="btn btn-ghost btn-sm"
              @click="showThreatPicker = !showThreatPicker"
            >
              Preloaded ({{ preloadedThreatScenarios.length }})
            </button>
            <button class="btn btn-ghost btn-sm" @click="triggerThreatLoad">Load</button>
            <input
              ref="threatFileInput"
              type="file"
              accept=".json"
              style="display: none"
              @change="handleThreatFileLoad"
              aria-label="Load threat scenario file"
              aria-hidden="true"
            />
          </div>
        </div>

        <!-- Preloaded Threat Picker -->
        <div v-if="showThreatPicker" class="scenario-picker">
          <div class="picker-header">
            <h4>Select Preloaded Threat Scenario</h4>
            <button class="btn btn-ghost btn-icon btn-sm" @click="showThreatPicker = false">×</button>
          </div>
          <div class="picker-list">
            <button
              v-for="scenario in preloadedThreatScenarios"
              :key="scenario.id"
              class="picker-item"
              @click="loadPreloadedThreat(scenario)"
            >
              <span class="picker-icon" :class="scenario.difficulty">⚔️</span>
              <div class="picker-info">
                <span class="picker-name">{{ scenario.name }}</span>
                <span class="picker-desc">{{ scenario.description }}</span>
                <span class="picker-meta">
                  <span class="difficulty-badge" :class="scenario.difficulty">{{ scenario.difficulty }}</span>
                  <span>{{ scenario.events.length }} events</span>
                </span>
              </div>
            </button>
          </div>
        </div>

        <div class="panel-content">
          <div v-if="!threatScenario" class="empty-state">
            <div class="empty-icon">⚔️</div>
            <p>No threat scenario loaded</p>
            <button class="btn btn-primary" @click="loadSampleThreats">Load Sample Threats</button>
          </div>

          <div v-else class="threat-list">
            <div
              v-for="event in threatScenario.events"
              :key="event.id"
              class="threat-item"
              :class="[event.status, event.severity]"
            >
              <div class="threat-timeline-marker">
                <div class="marker-time">{{ formatLogTime(event.startTime) }}</div>
                <div class="marker-line" :class="event.status"></div>
              </div>

              <div class="threat-card">
                <div class="threat-header">
                  <span class="threat-severity" :style="{ backgroundColor: getSeverityColor(event.severity) }">
                    {{ event.severity }}
                  </span>
                  <span class="threat-status" :class="event.status">{{ event.status }}</span>
                </div>
                <h4 class="threat-name">{{ event.name }}</h4>
                <p class="threat-description">{{ event.description }}</p>
                <div class="threat-meta">
                  <span class="meta-item">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    {{ event.duration }}min
                  </span>
                  <span class="meta-item">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                      <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                    {{ event.targetDevices.length }} targets
                  </span>
                  <span class="meta-item mitre">{{ event.attackVector }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Right Panel - Event Log & Stats -->
      <section class="panel log-panel">
        <div class="panel-header">
          <h3>Event Log</h3>
          <div v-if="simulationState === 'completed'" class="panel-actions">
            <button
              class="btn btn-primary btn-sm"
              @click="openSaveModal"
            >
              Save as Experiment
            </button>
            <button
              class="btn btn-ghost btn-sm"
              @click="exportResults"
            >
              Export JSON
            </button>
          </div>
        </div>

        <!-- Statistics -->
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ stats.totalEvents }}</div>
            <div class="stat-label">Total Events</div>
          </div>
          <div class="stat-card detected">
            <div class="stat-value">{{ stats.detectedThreats }}</div>
            <div class="stat-label">Detected</div>
          </div>
          <div class="stat-card blocked">
            <div class="stat-value">{{ stats.blockedThreats }}</div>
            <div class="stat-label">Blocked</div>
          </div>
          <div class="stat-card compromised">
            <div class="stat-value">{{ stats.compromisedDevices }}</div>
            <div class="stat-label">Compromised</div>
          </div>
        </div>

        <!-- Log entries -->
        <div class="panel-content log-content">
          <div v-if="eventLog.length === 0" class="empty-state small">
            <p>No events yet</p>
          </div>

          <div v-else class="event-log">
            <div
              v-for="event in eventLog"
              :key="event.id"
              class="log-entry"
              :class="event.type"
            >
              <span class="log-time">{{ formatLogTime(event.timestamp) }}</span>
              <span class="log-icon" :class="event.type">{{ getEventTypeIcon(event.type) }}</span>
              <span class="log-message">{{ event.message }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Custom Duration Dialog -->
    <div v-if="showCustomDurationDialog" class="modal-overlay" @click.self="cancelCustomDuration">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>Custom Duration</h3>
          <button class="btn btn-ghost btn-icon" @click="cancelCustomDuration">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="custom-duration">Duration in seconds:</label>
            <input
              id="custom-duration"
              v-model.number="customDurationSeconds"
              type="number"
              class="form-input"
              min="60"
              max="604800"
              placeholder="Enter seconds (min: 60)"
              @keyup.enter="applyCustomDuration"
            />
            <div class="duration-preview">
              = {{ Math.floor(customDurationSeconds / 3600) }}h {{ Math.floor((customDurationSeconds % 3600) / 60) }}m {{ customDurationSeconds % 60 }}s
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="cancelCustomDuration">Cancel</button>
          <button class="btn btn-primary" @click="applyCustomDuration" :disabled="customDurationSeconds < 60">Apply</button>
        </div>
      </div>
    </div>

    <!-- Save as Experiment Modal -->
    <div v-if="showSaveModal" class="modal-overlay" @click.self="closeSaveModal">
      <div class="modal">
        <div class="modal-header">
          <h3>Save as Experiment</h3>
          <button class="btn btn-ghost btn-icon" @click="closeSaveModal">×</button>
        </div>
        <div class="modal-body">
          <div v-if="saveSuccess" class="success-message">
            Experiment saved successfully!
          </div>
          <template v-else>
            <div class="form-group">
              <label for="exp-name">Name *</label>
              <input
                id="exp-name"
                v-model="saveForm.name"
                type="text"
                class="form-input"
                placeholder="Experiment name"
              />
            </div>
            <div class="form-group">
              <label for="exp-desc">Description</label>
              <textarea
                id="exp-desc"
                v-model="saveForm.description"
                class="form-input"
                rows="3"
                placeholder="Optional description"
              ></textarea>
            </div>
            <div class="form-group">
              <label for="exp-tags">Tags (comma-separated)</label>
              <input
                id="exp-tags"
                v-model="saveForm.tags"
                type="text"
                class="form-input"
                placeholder="e.g., threat, iot, security"
              />
            </div>
            <div v-if="saveError" class="error-message">{{ saveError }}</div>
          </template>
        </div>
        <div v-if="!saveSuccess" class="modal-footer">
          <button class="btn btn-ghost" @click="closeSaveModal" :disabled="isSaving">
            Cancel
          </button>
          <button class="btn btn-primary" @click="saveAsExperiment" :disabled="isSaving">
            {{ isSaving ? 'Saving...' : 'Save Experiment' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.simulation-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Header */
.simulation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  gap: var(--spacing-lg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-left h2 {
  margin: 0;
  font-size: 1.25rem;
}

.simulation-status {
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.simulation-status.idle {
  background: var(--bg-input);
  color: var(--text-secondary);
}

.simulation-status.running {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
}

.simulation-status.paused {
  background: rgba(234, 179, 8, 0.15);
  color: var(--color-warning);
}

.simulation-status.completed {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}

.header-center {
  flex: 1;
  max-width: 500px;
}

.time-display {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
  font-family: monospace;
}

.current-time {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.time-separator {
  color: var(--text-muted);
}

.total-time {
  font-size: 1rem;
  color: var(--text-secondary);
}

.progress-bar {
  position: relative;
  height: 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: visible;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-success));
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.threat-marker {
  position: absolute;
  top: -4px;
  transform: translateX(-50%);
  z-index: 1;
}

.marker-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid var(--bg-card);
}

.threat-marker.active .marker-dot {
  animation: pulse 1s infinite;
}

.threat-marker.completed .marker-dot,
.threat-marker.detected .marker-dot,
.threat-marker.blocked .marker-dot {
  opacity: 0.5;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

/* Mode Toggle */
.mode-toggle {
  display: flex;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.mode-toggle .mode-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.mode-toggle .mode-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}

.mode-toggle .mode-btn.active {
  background: var(--color-primary);
  color: white;
}

.mode-toggle .mode-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Duration control */
.duration-control {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.duration-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.duration-select {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.duration-select:hover:not(:disabled) {
  border-color: var(--color-primary);
}

.duration-select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.duration-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.custom-duration-badge {
  font-size: 0.7rem;
  color: var(--color-primary);
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  white-space: nowrap;
  margin-left: 4px;
}

/* Speed control */
.speed-control {
  display: flex;
  align-items: center;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  overflow: visible;
  position: relative;
}

.speed-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.speed-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}

.speed-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.speed-btn.active {
  background: var(--color-primary);
  color: white;
}

.custom-speed-btn {
  min-width: 32px;
}

.custom-speed-input {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
}

.custom-speed-input input {
  width: 60px;
  padding: 4px 6px;
  font-size: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-input);
  color: var(--text-primary);
}

.custom-speed-input .apply-btn {
  padding: 4px 8px;
  font-size: 0.7rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.custom-speed-input .apply-btn:hover {
  opacity: 0.9;
}

/* Duration estimate display */
.duration-estimate {
  font-size: 0.7rem;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  white-space: nowrap;
}

/* Modal small size */
.modal-sm {
  max-width: 320px;
}

.duration-preview {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.playback-controls {
  display: flex;
  gap: var(--spacing-xs);
}

/* Content */
.simulation-content {
  display: grid;
  grid-template-columns: 1fr 1fr 320px;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  flex: 1;
  overflow: hidden;
}

/* Panels */
.panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.panel-header h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.panel-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.panel-content {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-md);
}

/* Empty states */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--text-muted);
}

.empty-state.small {
  padding: var(--spacing-lg);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.empty-state p {
  margin-bottom: var(--spacing-md);
}

/* Home Visualization */
.home-visualization {
  position: relative;
  min-height: 400px;
}

.room {
  position: absolute;
  background: var(--bg-input);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.room-header {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-hover);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}

.room-devices {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
}

.device {
  position: relative;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  font-size: 1.25rem;
  transition: all var(--transition-fast);
}

.device.warning {
  border-color: var(--color-warning);
  animation: devicePulse 1s infinite;
}

.device.compromised {
  border-color: var(--color-danger);
  background: rgba(239, 68, 68, 0.1);
}

.device-indicator {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid var(--bg-card);
}

.inhabitant {
  position: absolute;
  font-size: 1.5rem;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  animation: float 2s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-5px); }
}

@keyframes devicePulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(234, 179, 8, 0); }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

.device-legend {
  display: flex;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.normal { background: var(--color-success); }
.legend-dot.warning { background: var(--color-warning); }
.legend-dot.compromised { background: var(--color-danger); }

/* Threat Timeline */
.threat-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.threat-item {
  display: flex;
  gap: var(--spacing-md);
}

.threat-timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 50px;
  flex-shrink: 0;
}

.marker-time {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.marker-line {
  flex: 1;
  width: 2px;
  background: var(--border-color);
  min-height: 60px;
}

.marker-line.active {
  background: var(--color-warning);
}

.marker-line.completed {
  background: var(--color-danger);
}

.marker-line.detected,
.marker-line.blocked {
  background: var(--color-success);
}

.threat-card {
  flex: 1;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--border-color);
}

.threat-item.active .threat-card {
  border-left-color: var(--color-warning);
  background: rgba(234, 179, 8, 0.05);
}

.threat-item.completed .threat-card {
  border-left-color: var(--color-danger);
}

.threat-item.detected .threat-card,
.threat-item.blocked .threat-card {
  border-left-color: var(--color-success);
}

.threat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.threat-severity {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  color: white;
}

.threat-status {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
}

.threat-status.active { color: var(--color-warning); }
.threat-status.completed { color: var(--color-danger); }
.threat-status.detected, .threat-status.blocked { color: var(--color-success); }

.threat-name {
  margin: 0 0 var(--spacing-xs);
  font-size: 0.85rem;
  font-weight: 600;
}

.threat-description {
  margin: 0 0 var(--spacing-sm);
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.threat-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.meta-item.mitre {
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-family: monospace;
}

/* Log Panel */
.log-panel {
  display: flex;
  flex-direction: column;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.stat-card {
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  text-align: center;
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

.stat-card.detected .stat-value { color: var(--color-primary); }
.stat-card.blocked .stat-value { color: var(--color-success); }
.stat-card.compromised .stat-value { color: var(--color-danger); }

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm) !important;
}

.event-log {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  background: var(--bg-input);
}

.log-entry.warning { background: rgba(234, 179, 8, 0.1); }
.log-entry.attack { background: rgba(239, 68, 68, 0.1); }
.log-entry.detection { background: rgba(34, 197, 94, 0.1); }

.log-time {
  font-family: monospace;
  color: var(--text-muted);
  flex-shrink: 0;
}

.log-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 700;
  flex-shrink: 0;
}

.log-icon.info { background: var(--bg-hover); color: var(--text-secondary); }
.log-icon.warning { background: rgba(234, 179, 8, 0.2); color: var(--color-warning); }
.log-icon.attack { background: rgba(239, 68, 68, 0.2); color: var(--color-danger); }
.log-icon.detection { background: rgba(34, 197, 94, 0.2); color: var(--color-success); }
.log-icon.system { background: var(--bg-hover); color: var(--text-muted); }

.log-message {
  flex: 1;
  color: var(--text-primary);
  line-height: 1.4;
}

/* Scenario Picker */
.scenario-picker {
  position: absolute;
  top: 40px;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  max-height: 300px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.picker-header h4 {
  margin: 0;
  font-size: 0.9rem;
}

.picker-list {
  overflow-y: auto;
  padding: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.picker-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: all var(--transition-fast);
}

.picker-item:hover {
  border-color: var(--color-primary);
  background: var(--bg-hover);
}

.picker-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.picker-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.picker-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.picker-desc {
  font-size: 0.7rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: 4px;
  font-size: 0.65rem;
  color: var(--text-muted);
}

.difficulty-badge {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  text-transform: uppercase;
}

.difficulty-badge.beginner {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
}

.difficulty-badge.intermediate {
  background: rgba(234, 179, 8, 0.15);
  color: var(--color-warning);
}

.difficulty-badge.advanced {
  background: rgba(249, 115, 22, 0.15);
  color: #f97316;
}

.difficulty-badge.expert {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

/* Ensure panels have relative position for picker */
.home-panel,
.threat-panel {
  position: relative;
}

/* Responsive */
@media (max-width: 1200px) {
  .simulation-content {
    grid-template-columns: 1fr 1fr;
  }

  .log-panel {
    grid-column: span 2;
    max-height: 250px;
  }

  .stats-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 768px) {
  .simulation-header {
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .header-center {
    width: 100%;
    max-width: none;
  }

  .simulation-content {
    grid-template-columns: 1fr;
  }

  .log-panel {
    grid-column: span 1;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  width: 100%;
  max-width: 450px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.modal-body {
  padding: var(--spacing-md);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-input {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

textarea.form-input {
  resize: vertical;
  min-height: 80px;
}

.error-message {
  padding: var(--spacing-sm);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  font-size: 0.85rem;
  margin-top: var(--spacing-sm);
}

.success-message {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--color-success);
  font-size: 1rem;
  font-weight: 500;
}
</style>
