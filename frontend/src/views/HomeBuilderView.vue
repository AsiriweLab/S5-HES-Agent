<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useDragAndDrop, useResizable } from '@/composables/useDragAndDrop'
import ScenarioBrowser from '@/components/ScenarioBrowser.vue'
import type { HomeScenario, ThreatScenario } from '@/services/PreloadedScenarioManager'

// Types
interface Room {
  id: string
  name: string
  type: RoomType
  x: number
  y: number
  width: number
  height: number
  devices: Device[]
}

interface Device {
  id: string
  name: string
  type: string
  icon: string
  x: number
  y: number
}

interface Inhabitant {
  id: string
  name: string
  role: InhabitantRole
  icon: string
  age: number
  schedule: DailySchedule
  devicePreferences: string[] // device types they commonly use
}

type InhabitantRole = 'adult' | 'child' | 'elderly' | 'guest' | 'pet'

interface DailySchedule {
  wakeUp: number // hour (0-23)
  sleep: number // hour (0-23)
  homeTime: number // hours at home per day
  workFromHome: boolean
  activeHours: number[] // hours when most active
}

interface InhabitantTemplate {
  role: InhabitantRole
  name: string
  icon: string
  description: string
  defaultAge: number
  defaultSchedule: DailySchedule
  defaultDevices: string[]
}

type RoomType =
  | 'living_room'
  | 'bedroom'
  | 'kitchen'
  | 'bathroom'
  | 'office'
  | 'garage'
  | 'hallway'
  | 'dining_room'
  | 'laundry'
  | 'storage'

interface HomeTemplate {
  id: string
  name: string
  description: string
  rooms: number
  devices: number
  icon: string
}

// State
const rooms = ref<Room[]>([])
const selectedRoom = ref<Room | null>(null)
const selectedDevice = ref<Device | null>(null)
const inhabitants = ref<Inhabitant[]>([])
const selectedInhabitant = ref<Inhabitant | null>(null)
const activeTab = ref<'rooms' | 'devices' | 'inhabitants'>('rooms')
const gridSize = ref(20)
const showGrid = ref(true)
const canvasRef = ref<HTMLElement | null>(null)
const draggedRoomId = ref<string | null>(null)
const resizingRoom = ref<Room | null>(null)

// Scenario Browser state
const showScenarioBrowser = ref(false)

// Undo/Redo history management
interface HistoryState {
  rooms: Room[]
  inhabitants: Inhabitant[]
}

const historyStack = ref<HistoryState[]>([])
const historyIndex = ref(-1)
const maxHistorySize = 50
const isUndoRedoAction = ref(false)

// Computed for undo/redo availability
const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value < historyStack.value.length - 1)

// Deep clone helper for state snapshots
function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

// Save current state to history
function saveToHistory() {
  if (isUndoRedoAction.value) return

  const currentState: HistoryState = {
    rooms: deepClone(rooms.value),
    inhabitants: deepClone(inhabitants.value),
  }

  // Remove any future states if we're in the middle of the history
  if (historyIndex.value < historyStack.value.length - 1) {
    historyStack.value = historyStack.value.slice(0, historyIndex.value + 1)
  }

  // Add current state
  historyStack.value.push(currentState)

  // Limit history size
  if (historyStack.value.length > maxHistorySize) {
    historyStack.value.shift()
  } else {
    historyIndex.value++
  }
}

// Restore state from history
function restoreFromHistory(state: HistoryState) {
  isUndoRedoAction.value = true

  rooms.value = deepClone(state.rooms)
  inhabitants.value = deepClone(state.inhabitants)

  // Clear selections
  selectedRoom.value = null
  selectedDevice.value = null
  selectedInhabitant.value = null

  // Select first room if available
  if (rooms.value.length > 0) {
    selectedRoom.value = rooms.value[0]
  }

  isUndoRedoAction.value = false
}

// Undo action
function undo() {
  if (!canUndo.value) return

  historyIndex.value--
  restoreFromHistory(historyStack.value[historyIndex.value])
}

// Redo action
function redo() {
  if (!canRedo.value) return

  historyIndex.value++
  restoreFromHistory(historyStack.value[historyIndex.value])
}

// Watch for changes to rooms and inhabitants to save history
// Use a debounced approach to avoid saving every small change
let saveHistoryTimeout: ReturnType<typeof setTimeout> | null = null

function debouncedSaveHistory() {
  if (isUndoRedoAction.value) return

  if (saveHistoryTimeout) {
    clearTimeout(saveHistoryTimeout)
  }

  saveHistoryTimeout = setTimeout(() => {
    saveToHistory()
  }, 300)
}

// Keyboard shortcuts for undo/redo
function handleKeyDown(event: KeyboardEvent) {
  // Check for Ctrl+Z (undo) or Cmd+Z on Mac
  if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
    event.preventDefault()
    undo()
  }
  // Check for Ctrl+Y (redo) or Ctrl+Shift+Z or Cmd+Shift+Z on Mac
  if ((event.ctrlKey || event.metaKey) && (event.key === 'y' || (event.key === 'z' && event.shiftKey))) {
    event.preventDefault()
    redo()
  }
}

// Inhabitant templates
const inhabitantTemplates: InhabitantTemplate[] = [
  {
    role: 'adult',
    name: 'Working Adult',
    icon: '👨',
    description: 'Full-time worker, standard schedule',
    defaultAge: 35,
    defaultSchedule: {
      wakeUp: 7,
      sleep: 23,
      homeTime: 12,
      workFromHome: false,
      activeHours: [7, 8, 18, 19, 20, 21, 22],
    },
    defaultDevices: ['smart_light', 'thermostat', 'tv', 'speaker'],
  },
  {
    role: 'adult',
    name: 'Remote Worker',
    icon: '👩‍💻',
    description: 'Works from home, always present',
    defaultAge: 30,
    defaultSchedule: {
      wakeUp: 8,
      sleep: 23,
      homeTime: 20,
      workFromHome: true,
      activeHours: [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
    },
    defaultDevices: ['smart_light', 'thermostat', 'camera', 'speaker'],
  },
  {
    role: 'child',
    name: 'Child',
    icon: '👧',
    description: 'School-age child',
    defaultAge: 10,
    defaultSchedule: {
      wakeUp: 7,
      sleep: 21,
      homeTime: 10,
      workFromHome: false,
      activeHours: [7, 15, 16, 17, 18, 19, 20],
    },
    defaultDevices: ['smart_light', 'tv', 'speaker'],
  },
  {
    role: 'elderly',
    name: 'Senior',
    icon: '👴',
    description: 'Retired, mostly at home',
    defaultAge: 70,
    defaultSchedule: {
      wakeUp: 6,
      sleep: 21,
      homeTime: 18,
      workFromHome: false,
      activeHours: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    },
    defaultDevices: ['smart_light', 'thermostat', 'door_sensor', 'smoke_detector'],
  },
  {
    role: 'guest',
    name: 'Guest',
    icon: '🧑‍🤝‍🧑',
    description: 'Temporary visitor',
    defaultAge: 35,
    defaultSchedule: {
      wakeUp: 9,
      sleep: 23,
      homeTime: 8,
      workFromHome: false,
      activeHours: [9, 10, 11, 18, 19, 20, 21, 22],
    },
    defaultDevices: ['smart_light', 'tv'],
  },
  {
    role: 'pet',
    name: 'Pet',
    icon: '🐕',
    description: 'Household pet',
    defaultAge: 5,
    defaultSchedule: {
      wakeUp: 6,
      sleep: 22,
      homeTime: 20,
      workFromHome: false,
      activeHours: [6, 7, 8, 12, 13, 17, 18, 19],
    },
    defaultDevices: ['camera', 'motion_sensor'],
  },
]

// Drag and drop for rooms
const { state: dragState, startDrag } = useDragAndDrop({
  gridSnap: gridSize.value,
  onDragMove: (x, y) => {
    if (draggedRoomId.value) {
      const room = rooms.value.find(r => r.id === draggedRoomId.value)
      if (room && canvasRef.value) {
        const rect = canvasRef.value.getBoundingClientRect()
        room.x = Math.max(0, x - rect.left - dragState.value.offsetX)
        room.y = Math.max(0, y - rect.top - dragState.value.offsetY)
      }
    }
  },
  onDragEnd: () => {
    draggedRoomId.value = null
  },
})

// Resize for rooms
const { startResize } = useResizable({
  minWidth: 80,
  minHeight: 60,
  maxWidth: 400,
  maxHeight: 300,
  gridSnap: gridSize.value,
  onResize: (width, height) => {
    if (resizingRoom.value) {
      resizingRoom.value.width = width
      resizingRoom.value.height = height
    }
  },
  onResizeEnd: () => {
    resizingRoom.value = null
  },
})

// Room types palette
const roomTypes: { type: RoomType; name: string; icon: string; color: string }[] = [
  { type: 'living_room', name: 'Living Room', icon: '🛋️', color: '#3b82f6' },
  { type: 'bedroom', name: 'Bedroom', icon: '🛏️', color: '#8b5cf6' },
  { type: 'kitchen', name: 'Kitchen', icon: '🍳', color: '#f59e0b' },
  { type: 'bathroom', name: 'Bathroom', icon: '🚿', color: '#06b6d4' },
  { type: 'office', name: 'Office', icon: '💼', color: '#10b981' },
  { type: 'garage', name: 'Garage', icon: '🚗', color: '#6b7280' },
  { type: 'hallway', name: 'Hallway', icon: '🚪', color: '#a855f7' },
  { type: 'dining_room', name: 'Dining Room', icon: '🍽️', color: '#ec4899' },
  { type: 'laundry', name: 'Laundry', icon: '🧺', color: '#14b8a6' },
  { type: 'storage', name: 'Storage', icon: '📦', color: '#78716c' },
]

// Device types - organized by category with frequently used first
// Icons map for device types
const deviceIcons: Record<string, string> = {
  // Frequently Used
  smart_light: '💡', smart_plug: '🔌', thermostat: '🌡️', security_camera: '📷',
  smart_lock: '🔒', motion_sensor: '📡', smart_speaker: '🔊', smart_tv: '📺',
  smart_doorbell: '🔔', door_sensor: '🚪', smoke_detector: '🚨', router: '📶',
  // Security
  window_sensor: '🪟', glass_break_sensor: '💥', panic_button: '🆘', siren_alarm: '🔔',
  safe_lock: '🔐', garage_door_controller: '🚗', security_keypad: '⌨️', video_doorbell_pro: '🎥',
  floodlight_camera: '🔦', ptz_camera: '🎬', indoor_camera: '📹', driveway_sensor: '🛣️',
  // Lighting
  smart_bulb_color: '🌈', smart_bulb_white: '💡', light_strip: '✨', smart_switch: '🔘',
  smart_dimmer: '🎚️', smart_blinds: '🪟', smart_curtains: '🪟', ceiling_fan_light: '💨',
  // Climate
  smart_thermostat_pro: '🌡️', temperature_sensor: '🌡️', humidity_sensor: '💧',
  air_quality_monitor: '🌬️', smart_fan: '💨', smart_ac: '❄️', smart_heater: '🔥',
  smart_humidifier: '💨', smart_dehumidifier: '💨', hvac_controller: '🏠',
  // Entertainment
  streaming_device: '📱', soundbar: '🔊', smart_display: '🖥️', gaming_console: '🎮',
  media_server: '📀', smart_projector: '📽️', multi_room_audio: '🎵', smart_remote: '📟',
  // Kitchen
  smart_refrigerator: '🧊', smart_oven: '🍳', smart_microwave: '📦', smart_coffee_maker: '☕',
  smart_kettle: '🫖', smart_toaster: '🍞', smart_blender: '🥤', smart_dishwasher: '🍽️',
  smart_faucet: '🚰', smart_scale_kitchen: '⚖️',
  // Appliances
  smart_washer: '🧺', smart_dryer: '🧺', smart_iron: '👔', smart_sewing_machine: '🧵',
  smart_water_heater: '🔥', smart_garbage_disposal: '🗑️',
  // Health
  smart_scale: '⚖️', blood_pressure_monitor: '❤️', sleep_tracker: '😴',
  smart_pill_dispenser: '💊', air_purifier: '🌬️', smart_mattress: '🛏️',
  fitness_tracker_dock: '⌚', smart_mirror: '🪞',
  // Energy
  smart_meter: '📊', solar_inverter: '☀️', battery_storage: '🔋', ev_charger: '⚡',
  energy_monitor: '📈', smart_circuit_breaker: '⚡',
  // Network
  hub: '📡', mesh_node: '📶', smart_bridge: '🌉', network_switch: '🔀',
  range_extender: '📡', nas_storage: '💾',
  // Outdoor
  smart_sprinkler: '💦', pool_controller: '🏊', weather_station: '🌤️', outdoor_light: '💡',
  gate_controller: '🚧', smart_grill: '🔥', garden_sensor: '🌱', pest_repeller: '🐜',
  // Cleaning
  robot_vacuum: '🤖', robot_mop: '🧹', window_cleaner: '🪟', pool_cleaner: '🏊',
  // Baby & Pet
  baby_monitor: '👶', smart_crib: '🍼', pet_feeder: '🐕', pet_camera: '📹',
  pet_door: '🚪', pet_tracker: '📍',
  // Accessibility
  voice_assistant_hub: '🗣️', automated_door: '🚪', emergency_alert: '🆘', hearing_loop: '👂',
  // Safety
  co_detector: '⚠️', water_leak_sensor: '💧', flood_sensor: '🌊', radon_detector: '☢️',
}

// Device categories for UI organization
interface DeviceCategory {
  id: string
  name: string
  icon: string
  priority: number
  device_count: number
}

interface CategorizedDevice {
  id: string
  name: string
  category: string
}

// Reactive state for categorized devices from API
const deviceCategories = ref<DeviceCategory[]>([])
const devicesByCategory = ref<Record<string, CategorizedDevice[]>>({})
const deviceTypesLoading = ref(true)
const activeDeviceCategory = ref<string>('frequently_used')

// Computed: get devices for active category
const devicesForActiveCategory = computed(() => {
  return devicesByCategory.value[activeDeviceCategory.value] || []
})

// Fetch device types from API
async function fetchDeviceTypes() {
  try {
    const response = await fetch('http://localhost:8000/api/simulation/device-types/categorized')
    if (response.ok) {
      const data = await response.json()
      deviceCategories.value = data.categories
      devicesByCategory.value = data.devices_by_category
      // Set first category as active (should be frequently_used)
      if (data.categories.length > 0) {
        activeDeviceCategory.value = data.categories[0].id
      }
    }
  } catch (err) {
    console.error('Failed to fetch device types:', err)
  } finally {
    deviceTypesLoading.value = false
  }
}

// Legacy device types for backward compatibility (used in recommendations)
const deviceTypes = [
  { type: 'smart_light', name: 'Smart Light', icon: '💡', category: 'lighting' },
  { type: 'thermostat', name: 'Thermostat', icon: '🌡️', category: 'climate' },
  { type: 'camera', name: 'Security Camera', icon: '📷', category: 'security' },
  { type: 'door_lock', name: 'Smart Lock', icon: '🔒', category: 'security' },
  { type: 'motion_sensor', name: 'Motion Sensor', icon: '📡', category: 'sensor' },
  { type: 'door_sensor', name: 'Door Sensor', icon: '🚪', category: 'sensor' },
  { type: 'smart_plug', name: 'Smart Plug', icon: '🔌', category: 'power' },
  { type: 'speaker', name: 'Smart Speaker', icon: '🔊', category: 'entertainment' },
  { type: 'tv', name: 'Smart TV', icon: '📺', category: 'entertainment' },
  { type: 'smoke_detector', name: 'Smoke Detector', icon: '🚨', category: 'safety' },
  { type: 'water_sensor', name: 'Water Sensor', icon: '💧', category: 'sensor' },
  { type: 'blinds', name: 'Smart Blinds', icon: '🪟', category: 'comfort' },
]

// Helper to get device icon
function getDeviceIcon(deviceType: string): string {
  return deviceIcons[deviceType] || '📱'
}

// Templates
const templates: HomeTemplate[] = [
  { id: 'studio', name: 'Studio Apartment', description: '1 room, minimal devices', rooms: 1, devices: 5, icon: '🏠' },
  { id: 'one_bed', name: 'One Bedroom', description: '3-4 rooms, basic setup', rooms: 4, devices: 12, icon: '🏡' },
  { id: 'two_bed', name: 'Two Bedroom', description: '5-6 rooms, standard setup', rooms: 6, devices: 20, icon: '🏘️' },
  { id: 'family', name: 'Family House', description: '8-10 rooms, full setup', rooms: 10, devices: 35, icon: '🏰' },
  { id: 'smart_mansion', name: 'Smart Mansion', description: '15+ rooms, extensive automation', rooms: 15, devices: 60, icon: '🏛️' },
  { id: 'security_focus', name: 'High Security Home', description: 'Security-focused setup', rooms: 5, devices: 25, icon: '🔐' },
  { id: 'energy_efficient', name: 'Energy Smart Home', description: 'Climate & energy focus', rooms: 6, devices: 22, icon: '🌱' },
  { id: 'elderly_care', name: 'Assisted Living', description: 'Safety sensors & alerts', rooms: 4, devices: 18, icon: '♿' },
]

// Device recommendations per room type
const roomDeviceRecommendations: Record<RoomType, string[]> = {
  living_room: ['smart_light', 'thermostat', 'tv', 'speaker', 'motion_sensor'],
  bedroom: ['smart_light', 'blinds', 'motion_sensor'],
  kitchen: ['smart_light', 'smoke_detector', 'water_sensor', 'smart_plug'],
  bathroom: ['smart_light', 'water_sensor', 'motion_sensor'],
  office: ['smart_light', 'thermostat', 'smart_plug', 'camera'],
  garage: ['smart_light', 'door_sensor', 'camera', 'motion_sensor'],
  hallway: ['smart_light', 'motion_sensor', 'door_sensor'],
  dining_room: ['smart_light', 'speaker', 'blinds'],
  laundry: ['smart_light', 'water_sensor', 'smart_plug'],
  storage: ['smart_light', 'motion_sensor'],
}

// Computed
const totalDevices = computed(() =>
  rooms.value.reduce((sum, room) => sum + room.devices.length, 0)
)

const canvasStyle = computed(() => ({
  backgroundSize: showGrid.value ? `${gridSize.value}px ${gridSize.value}px` : 'none',
}))

// Methods
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function addRoom(type: RoomType) {
  const roomType = roomTypes.find(r => r.type === type)
  if (!roomType) return

  const newRoom: Room = {
    id: generateId(),
    name: `${roomType.name} ${rooms.value.filter(r => r.type === type).length + 1}`,
    type,
    x: 50 + (rooms.value.length % 3) * 150,
    y: 50 + Math.floor(rooms.value.length / 3) * 120,
    width: 140,
    height: 100,
    devices: [],
  }

  rooms.value.push(newRoom)
  selectedRoom.value = newRoom
}

function deleteRoom(roomId: string) {
  const index = rooms.value.findIndex(r => r.id === roomId)
  if (index !== -1) {
    rooms.value.splice(index, 1)
    if (selectedRoom.value?.id === roomId) {
      selectedRoom.value = null
    }
  }
}

function addDeviceToRoom(deviceType: string, room: Room) {
  const device = deviceTypes.find(d => d.type === deviceType)
  if (!device) return

  const newDevice: Device = {
    id: generateId(),
    name: `${device.name} ${room.devices.filter(d => d.type === deviceType).length + 1}`,
    type: deviceType,
    icon: device.icon,
    x: 10 + (room.devices.length % 3) * 40,
    y: 30 + Math.floor(room.devices.length / 3) * 30,
  }

  room.devices.push(newDevice)
  selectedDevice.value = newDevice
}

// Add categorized device to room (from API-fetched device types)
function addCategorizedDeviceToRoom(device: CategorizedDevice, room: Room) {
  const newDevice: Device = {
    id: generateId(),
    name: `${device.name} ${room.devices.filter(d => d.type === device.id).length + 1}`,
    type: device.id,
    icon: getDeviceIcon(device.id),
    x: 10 + (room.devices.length % 3) * 40,
    y: 30 + Math.floor(room.devices.length / 3) * 30,
  }

  room.devices.push(newDevice)
  selectedDevice.value = newDevice
}

function removeDeviceFromRoom(deviceId: string, room: Room) {
  const index = room.devices.findIndex(d => d.id === deviceId)
  if (index !== -1) {
    room.devices.splice(index, 1)
    if (selectedDevice.value?.id === deviceId) {
      selectedDevice.value = null
    }
  }
}

// Inhabitant management
function addInhabitant(template: InhabitantTemplate) {
  const newInhabitant: Inhabitant = {
    id: generateId(),
    name: `${template.name} ${inhabitants.value.filter(i => i.role === template.role).length + 1}`,
    role: template.role,
    icon: template.icon,
    age: template.defaultAge,
    schedule: { ...template.defaultSchedule },
    devicePreferences: [...template.defaultDevices],
  }

  inhabitants.value.push(newInhabitant)
  selectedInhabitant.value = newInhabitant
}

function removeInhabitant(inhabitantId: string) {
  const index = inhabitants.value.findIndex(i => i.id === inhabitantId)
  if (index !== -1) {
    inhabitants.value.splice(index, 1)
    if (selectedInhabitant.value?.id === inhabitantId) {
      selectedInhabitant.value = null
    }
  }
}

function formatHour(hour: number): string {
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const h = hour % 12 || 12
  return `${h}:00 ${ampm}`
}

function getRoleColor(role: InhabitantRole): string {
  const colors: Record<InhabitantRole, string> = {
    adult: '#3b82f6',
    child: '#f59e0b',
    elderly: '#8b5cf6',
    guest: '#10b981',
    pet: '#ec4899',
  }
  return colors[role]
}

// Helper to add devices to a room based on recommendations
function autoPopulateDevices(room: Room, maxDevices = 3) {
  const recommendations = roomDeviceRecommendations[room.type] || ['smart_light']
  const devicesToAdd = recommendations.slice(0, maxDevices)

  devicesToAdd.forEach(deviceType => {
    const device = deviceTypes.find(d => d.type === deviceType)
    if (device) {
      const newDevice: Device = {
        id: generateId(),
        name: `${device.name}`,
        type: deviceType,
        icon: device.icon,
        x: 10 + (room.devices.length % 3) * 40,
        y: 30 + Math.floor(room.devices.length / 3) * 30,
      }
      room.devices.push(newDevice)
    }
  })
}

function loadTemplate(templateId: string) {
  // Clear existing rooms and inhabitants
  rooms.value = []
  selectedRoom.value = null
  selectedDevice.value = null
  inhabitants.value = []
  selectedInhabitant.value = null

  // Generate rooms based on template
  const template = templates.find(t => t.id === templateId)
  if (!template) return

  // Define room configurations for each template
  const templateConfigs: Record<string, { rooms: { type: RoomType; count: number }[]; devicesPerRoom: number; addInhabitants?: boolean }> = {
    studio: {
      rooms: [{ type: 'living_room', count: 1 }],
      devicesPerRoom: 5,
    },
    one_bed: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 1 },
        { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 1 },
      ],
      devicesPerRoom: 3,
    },
    two_bed: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 2 },
        { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 2 },
      ],
      devicesPerRoom: 3,
    },
    family: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 4 },
        { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 3 },
        { type: 'garage', count: 1 },
      ],
      devicesPerRoom: 3,
      addInhabitants: true,
    },
    smart_mansion: {
      rooms: [
        { type: 'living_room', count: 2 },
        { type: 'bedroom', count: 5 },
        { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 4 },
        { type: 'office', count: 2 },
        { type: 'garage', count: 1 },
      ],
      devicesPerRoom: 4,
      addInhabitants: true,
    },
    security_focus: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 2 },
        { type: 'hallway', count: 2 },
        { type: 'garage', count: 1 },
      ],
      devicesPerRoom: 4,
    },
    energy_efficient: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 2 },
        { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 1 },
        { type: 'office', count: 1 },
      ],
      devicesPerRoom: 3,
    },
    elderly_care: {
      rooms: [
        { type: 'living_room', count: 1 },
        { type: 'bedroom', count: 1 },
        { type: 'bathroom', count: 1 },
        { type: 'kitchen', count: 1 },
      ],
      devicesPerRoom: 4,
    },
  }

  const config = templateConfigs[templateId] || templateConfigs.one_bed

  // Create rooms with auto-populated devices
  config.rooms.forEach(({ type, count }) => {
    for (let i = 0; i < count; i++) {
      const roomType = roomTypes.find(r => r.type === type)
      if (!roomType) continue

      const newRoom: Room = {
        id: generateId(),
        name: `${roomType.name} ${rooms.value.filter(r => r.type === type).length + 1}`,
        type,
        x: 50 + (rooms.value.length % 4) * 160,
        y: 50 + Math.floor(rooms.value.length / 4) * 130,
        width: 140,
        height: 100,
        devices: [],
      }

      rooms.value.push(newRoom)
      autoPopulateDevices(newRoom, config.devicesPerRoom)
    }
  })

  // Add sample inhabitants for family templates
  if (config.addInhabitants) {
    const adultTemplate = inhabitantTemplates.find(t => t.name === 'Working Adult')
    const childTemplate = inhabitantTemplates.find(t => t.role === 'child')
    if (adultTemplate) {
      addInhabitant(adultTemplate)
      addInhabitant(adultTemplate)
    }
    if (childTemplate && templateId === 'family') {
      addInhabitant(childTemplate)
    }
  }

  selectedRoom.value = rooms.value[0] || null

  // Auto-sync to backend after loading template
  syncToBackend()
}

function clearAll() {
  if (confirm('Are you sure you want to clear all rooms, devices, and inhabitants?')) {
    rooms.value = []
    selectedRoom.value = null
    selectedDevice.value = null
    inhabitants.value = []
    selectedInhabitant.value = null
  }
}

// Backend sync state
const syncStatus = ref<'idle' | 'syncing' | 'synced' | 'error'>('idle')
const syncError = ref<string | null>(null)

async function syncToBackend() {
  syncStatus.value = 'syncing'
  syncError.value = null

  try {
    const payload = {
      name: `Home Builder - ${new Date().toLocaleDateString()}`,
      rooms: rooms.value.map(room => ({
        id: room.id,
        name: room.name,
        type: room.type,
        x: room.x,
        y: room.y,
        width: room.width,
        height: room.height,
        devices: room.devices.map(d => ({
          id: d.id,
          name: d.name,
          type: d.type,
          icon: d.icon,
          x: d.x,
          y: d.y,
        })),
      })),
      inhabitants: inhabitants.value.map(inh => ({
        id: inh.id,
        name: inh.name,
        role: inh.role,
        age: inh.age,
        schedule: inh.schedule,
      })),
    }

    const response = await fetch('http://localhost:8000/api/simulation/home/custom', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    syncStatus.value = 'synced'
    return true
  } catch (err) {
    syncStatus.value = 'error'
    syncError.value = err instanceof Error ? err.message : 'Unknown error'
    console.error('Failed to sync to backend:', err)
    return false
  }
}

async function saveConfiguration() {
  // First, sync to backend so experiments can import the configuration
  await syncToBackend()

  // Then download the JSON file
  const config = {
    rooms: rooms.value,
    inhabitants: inhabitants.value,
    createdAt: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `home-config-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// File input ref for loading configurations
const fileInputRef = ref<HTMLInputElement | null>(null)

function triggerFileLoad() {
  fileInputRef.value?.click()
}

function handleFileLoad(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const config = JSON.parse(content)

      // Validate the configuration structure
      if (!config.rooms || !Array.isArray(config.rooms)) {
        alert('Invalid configuration file: missing rooms array')
        return
      }

      // Clear existing data
      rooms.value = []
      inhabitants.value = []
      selectedRoom.value = null
      selectedDevice.value = null
      selectedInhabitant.value = null

      // Load rooms with validation
      config.rooms.forEach((room: Room) => {
        if (room.id && room.name && room.type) {
          // Ensure devices array exists
          if (!room.devices) room.devices = []
          rooms.value.push(room)
        }
      })

      // Load inhabitants if present
      if (config.inhabitants && Array.isArray(config.inhabitants)) {
        config.inhabitants.forEach((inhabitant: Inhabitant) => {
          if (inhabitant.id && inhabitant.name && inhabitant.role) {
            inhabitants.value.push(inhabitant)
          }
        })
      }

      // Select first room if available
      if (rooms.value.length > 0) {
        selectedRoom.value = rooms.value[0]
      }

      alert(`Loaded ${rooms.value.length} rooms and ${inhabitants.value.length} inhabitants`)
    } catch (err) {
      console.error('Failed to parse configuration file:', err)
      alert('Failed to load configuration: Invalid JSON format')
    }
  }
  reader.readAsText(file)

  // Reset input to allow loading the same file again
  input.value = ''
}

function getRoomColor(type: RoomType): string {
  return roomTypes.find(r => r.type === type)?.color || '#6b7280'
}

function getRoomIcon(type: RoomType): string {
  return roomTypes.find(r => r.type === type)?.icon || '🏠'
}

// Load preloaded scenario from browser
function loadPreloadedScenario(scenario: HomeScenario | ThreatScenario) {
  // Only handle home scenarios
  if (!('homeType' in scenario) || !('rooms' in scenario)) {
    console.warn('Received non-home scenario in HomeBuilder')
    return
  }

  const homeScenario = scenario as HomeScenario

  // Clear existing data
  rooms.value = []
  inhabitants.value = []
  selectedRoom.value = null
  selectedDevice.value = null
  selectedInhabitant.value = null

  // Load rooms from the scenario
  homeScenario.rooms.forEach((scenarioRoom, index) => {
    const newRoom: Room = {
      id: scenarioRoom.id || generateId(),
      name: scenarioRoom.name,
      type: scenarioRoom.type as RoomType,
      x: scenarioRoom.x ?? (50 + (index % 4) * 160),
      y: scenarioRoom.y ?? (50 + Math.floor(index / 4) * 130),
      width: scenarioRoom.width ?? 140,
      height: scenarioRoom.height ?? 100,
      devices: (scenarioRoom.devices || []).map(dev => ({
        id: dev.id || generateId(),
        name: dev.name,
        type: dev.type,
        icon: dev.icon || deviceTypes.find(d => d.type === dev.type)?.icon || '📱',
        x: dev.x ?? 10,
        y: dev.y ?? 30,
      })),
    }
    rooms.value.push(newRoom)
  })

  // Load inhabitants from the scenario
  homeScenario.inhabitants.forEach(inhabitant => {
    const newInhabitant: Inhabitant = {
      id: inhabitant.id || generateId(),
      name: inhabitant.name,
      role: inhabitant.role as InhabitantRole,
      icon: inhabitant.icon || '👤',
      age: inhabitant.age ?? 30,
      schedule: inhabitant.schedule ?? {
        wakeUp: 7,
        sleep: 23,
        homeTime: 12,
        workFromHome: false,
        activeHours: [7, 8, 18, 19, 20, 21, 22],
      },
      devicePreferences: inhabitant.devicePreferences || [],
    }
    inhabitants.value.push(newInhabitant)
  })

  // Select first room if available
  if (rooms.value.length > 0) {
    selectedRoom.value = rooms.value[0]
  }

  showScenarioBrowser.value = false

  // Auto-sync to backend after loading scenario
  syncToBackend()
}

// Load home created from chat action (via sessionStorage)
function loadChatCreatedHome() {
  const savedData = sessionStorage.getItem('chatCreatedHome')
  if (!savedData) return false

  try {
    const createdHome = JSON.parse(savedData)

    // Clear existing data
    rooms.value = []
    inhabitants.value = []
    selectedRoom.value = null
    selectedDevice.value = null
    selectedInhabitant.value = null

    // Load rooms from the created home
    createdHome.rooms.forEach((room: { id: string; name: string; room_type: string; floor?: number; devices?: Array<{ id: string; name: string; device_type: string }> }, index: number) => {
      const newRoom: Room = {
        id: room.id || generateId(),
        name: room.name,
        type: room.room_type as RoomType,
        x: 50 + (index % 4) * 160,
        y: 50 + Math.floor(index / 4) * 130,
        width: 140,
        height: 100,
        devices: (room.devices || []).map(dev => ({
          id: dev.id || generateId(),
          name: dev.name,
          type: dev.device_type,
          icon: deviceTypes.find(d => d.type === dev.device_type)?.icon || '📱',
          x: 10,
          y: 30,
        })),
      }
      rooms.value.push(newRoom)
    })

    // Load inhabitants from the created home
    createdHome.inhabitants.forEach((inhabitant: { id: string; name: string; role: string }) => {
      const template = inhabitantTemplates.find(t => t.role === inhabitant.role) || inhabitantTemplates[0]
      const newInhabitant: Inhabitant = {
        id: inhabitant.id || generateId(),
        name: inhabitant.name,
        role: inhabitant.role as InhabitantRole,
        icon: template.icon,
        age: template.defaultAge,
        schedule: { ...template.defaultSchedule },
        devicePreferences: [...template.defaultDevices],
      }
      inhabitants.value.push(newInhabitant)
    })

    // Select first room if available
    if (rooms.value.length > 0) {
      selectedRoom.value = rooms.value[0]
    }

    // Clear the sessionStorage after loading
    sessionStorage.removeItem('chatCreatedHome')

    console.log(`[HomeBuilder] Loaded chat-created home: ${createdHome.name} with ${rooms.value.length} rooms`)
    return true
  } catch (err) {
    console.error('[HomeBuilder] Failed to load chat-created home:', err)
    sessionStorage.removeItem('chatCreatedHome')
    return false
  }
}

// Drag handlers
function handleRoomDragStart(event: MouseEvent, room: Room) {
  // Don't start drag if clicking on delete button
  if ((event.target as HTMLElement).closest('.room-delete')) return
  // Don't start drag if clicking on resize handle
  if ((event.target as HTMLElement).closest('.resize-handle')) return

  draggedRoomId.value = room.id
  selectedRoom.value = room

  // Calculate offset from room corner
  const roomElement = event.currentTarget as HTMLElement
  const rect = roomElement.getBoundingClientRect()
  const offsetX = event.clientX - rect.left
  const offsetY = event.clientY - rect.top

  startDrag(event, room, 'room', offsetX, offsetY)
}

function handleRoomResizeStart(event: MouseEvent, room: Room, direction: string) {
  event.stopPropagation()
  resizingRoom.value = room
  selectedRoom.value = room
  startResize(event, direction, room.width, room.height)
}

// On mount, check for chat-created home data and set up keyboard listeners
onMounted(() => {
  loadChatCreatedHome()

  // Add keyboard listener for undo/redo shortcuts
  window.addEventListener('keydown', handleKeyDown)

  // Initialize history with empty state
  saveToHistory()

  // Fetch categorized device types from API
  fetchDeviceTypes()
})

// Cleanup keyboard listener
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  if (saveHistoryTimeout) {
    clearTimeout(saveHistoryTimeout)
  }
})

// Watch for changes to save history (deep watch on rooms and inhabitants)
watch(
  () => [rooms.value.length, inhabitants.value.length],
  () => {
    debouncedSaveHistory()
  }
)

// Also watch for structural changes within rooms (device additions/removals)
watch(
  () => rooms.value.map(r => r.devices.length).join(','),
  () => {
    debouncedSaveHistory()
  }
)
</script>

<template>
  <div class="home-builder">
    <!-- Header -->
    <div class="builder-header">
      <div class="header-left">
        <h2>Home Builder</h2>
        <span class="stats">
          {{ rooms.length }} rooms, {{ totalDevices }} devices
        </span>
      </div>
      <div class="header-actions">
        <!-- Undo/Redo buttons -->
        <button
          class="btn btn-ghost"
          :disabled="!canUndo"
          @click="undo"
          title="Undo (Ctrl+Z)"
          aria-label="Undo"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 7v6h6"></path>
            <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"></path>
          </svg>
        </button>
        <button
          class="btn btn-ghost"
          :disabled="!canRedo"
          @click="redo"
          title="Redo (Ctrl+Y)"
          aria-label="Redo"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 7v6h-6"></path>
            <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"></path>
          </svg>
        </button>
        <div class="header-divider"></div>
        <button class="btn btn-ghost" @click="showScenarioBrowser = true" title="Browse preloaded home scenarios">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
          Scenarios
        </button>
        <button class="btn btn-ghost" @click="showGrid = !showGrid">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
          Grid
        </button>
        <button class="btn btn-ghost" @click="clearAll">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          Clear
        </button>
        <button class="btn btn-ghost" @click="triggerFileLoad">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          Load
        </button>
        <button
          class="btn sync-btn"
          :class="{ 'btn-success': syncStatus === 'synced', 'btn-danger': syncStatus === 'error', 'btn-ghost': syncStatus === 'idle' || syncStatus === 'syncing' }"
          @click="syncToBackend"
          :disabled="syncStatus === 'syncing' || rooms.length === 0"
          :title="syncStatus === 'synced' ? 'Configuration synced to simulation' : syncStatus === 'error' ? (syncError ?? 'Sync failed') : 'Sync to simulation backend'"
        >
          <svg v-if="syncStatus === 'syncing'" class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
          </svg>
          <svg v-else-if="syncStatus === 'synced'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <svg v-else-if="syncStatus === 'error'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6"></path>
            <path d="M1 20v-6h6"></path>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"></path>
            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14"></path>
          </svg>
          {{ syncStatus === 'syncing' ? 'Syncing...' : syncStatus === 'synced' ? 'Synced' : syncStatus === 'error' ? 'Error' : 'Sync' }}
        </button>
        <button class="btn btn-primary" @click="saveConfiguration">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
            <polyline points="17 21 17 13 7 13 7 21"></polyline>
            <polyline points="7 3 7 8 15 8"></polyline>
          </svg>
          Save
        </button>
        <!-- Hidden file input for loading configurations -->
        <input
          ref="fileInputRef"
          type="file"
          accept=".json"
          style="display: none"
          @change="handleFileLoad"
        />
      </div>
    </div>

    <div class="builder-content">
      <!-- Left Sidebar - Palette -->
      <aside class="palette-sidebar">
        <!-- Tabs -->
        <div class="palette-tabs">
          <button
            :class="['tab', { active: activeTab === 'rooms' }]"
            @click="activeTab = 'rooms'"
          >
            Rooms
          </button>
          <button
            :class="['tab', { active: activeTab === 'devices' }]"
            @click="activeTab = 'devices'"
          >
            Devices
          </button>
          <button
            :class="['tab', { active: activeTab === 'inhabitants' }]"
            @click="activeTab = 'inhabitants'"
          >
            People
          </button>
        </div>

        <!-- Room Types -->
        <div v-if="activeTab === 'rooms'" class="palette-content">
          <div class="palette-section">
            <h4>Room Types</h4>
            <div class="palette-grid">
              <button
                v-for="room in roomTypes"
                :key="room.type"
                class="palette-item"
                @click="addRoom(room.type)"
                :title="room.name"
              >
                <span class="item-icon">{{ room.icon }}</span>
                <span class="item-label">{{ room.name }}</span>
              </button>
            </div>
          </div>

          <div class="palette-section">
            <h4>Templates</h4>
            <div class="template-list">
              <button
                v-for="template in templates"
                :key="template.id"
                class="template-item"
                @click="loadTemplate(template.id)"
              >
                <span class="template-icon">{{ template.icon }}</span>
                <div class="template-info">
                  <span class="template-name">{{ template.name }}</span>
                  <span class="template-desc">{{ template.description }}</span>
                </div>
              </button>
            </div>
          </div>
        </div>

        <!-- Device Types - Categorized with Frequently Used First -->
        <div v-else-if="activeTab === 'devices'" class="palette-content">
          <p v-if="!selectedRoom" class="hint">Select a room first to add devices</p>
          <div v-else-if="deviceTypesLoading" class="hint">Loading device types...</div>
          <template v-else>
            <!-- Category tabs for quick navigation -->
            <div class="device-category-tabs">
              <button
                v-for="category in deviceCategories"
                :key="category.id"
                :class="['category-tab', { active: activeDeviceCategory === category.id }]"
                @click="activeDeviceCategory = category.id"
                :title="`${category.name} (${category.device_count} devices)`"
              >
                {{ category.name }}
              </button>
            </div>

            <!-- Devices for active category -->
            <div class="palette-section">
              <h4>{{ deviceCategories.find(c => c.id === activeDeviceCategory)?.name || 'Devices' }} ({{ devicesForActiveCategory.length }})</h4>
              <div class="palette-grid">
                <button
                  v-for="device in devicesForActiveCategory"
                  :key="device.id"
                  class="palette-item"
                  @click="addCategorizedDeviceToRoom(device, selectedRoom)"
                  :title="device.name"
                >
                  <span class="item-icon">{{ getDeviceIcon(device.id) }}</span>
                  <span class="item-label">{{ device.name }}</span>
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- Inhabitants -->
        <div v-else class="palette-content">
          <div class="palette-section">
            <h4>Add Inhabitants</h4>
            <p class="section-description">
              Inhabitants define who lives in the home and their daily patterns. They affect simulation behavior like device usage and activity times.
            </p>
            <div class="inhabitant-template-list">
              <button
                v-for="template in inhabitantTemplates"
                :key="template.name"
                class="inhabitant-template-item"
                @click="addInhabitant(template)"
              >
                <span class="template-icon" :style="{ backgroundColor: `${getRoleColor(template.role)}20` }">
                  {{ template.icon }}
                </span>
                <div class="template-info">
                  <span class="template-name">{{ template.name }}</span>
                  <span class="template-desc">{{ template.description }}</span>
                </div>
              </button>
            </div>
          </div>

          <div class="palette-section">
            <h4>Current Inhabitants ({{ inhabitants.length }})</h4>
            <div v-if="inhabitants.length === 0" class="hint">
              No inhabitants added yet. Click above to add people to your home.
            </div>
            <div v-else class="current-inhabitants-list">
              <div
                v-for="inhabitant in inhabitants"
                :key="inhabitant.id"
                class="current-inhabitant-item"
                :class="{ selected: selectedInhabitant?.id === inhabitant.id }"
                @click="selectedInhabitant = inhabitant"
              >
                <span class="inhabitant-icon">{{ inhabitant.icon }}</span>
                <div class="inhabitant-info">
                  <span class="inhabitant-name">{{ inhabitant.name }}</span>
                  <span class="inhabitant-role" :style="{ color: getRoleColor(inhabitant.role) }">
                    {{ inhabitant.role }}
                  </span>
                </div>
                <button
                  class="btn btn-ghost btn-icon btn-sm"
                  @click.stop="removeInhabitant(inhabitant.id)"
                  title="Remove inhabitant"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Canvas -->
      <main class="canvas-area">
        <div
          ref="canvasRef"
          class="canvas"
          :class="{ 'show-grid': showGrid, dragging: dragState.isDragging }"
          :style="canvasStyle"
        >
          <!-- Empty State -->
          <div v-if="rooms.length === 0" class="empty-canvas">
            <div class="empty-icon">🏠</div>
            <h3>Start Building Your Smart Home</h3>
            <p>Click room types from the palette or select a template to get started</p>
          </div>

          <!-- Rooms -->
          <div
            v-for="room in rooms"
            :key="room.id"
            class="room"
            :class="{
              selected: selectedRoom?.id === room.id,
              dragging: draggedRoomId === room.id,
              resizing: resizingRoom?.id === room.id
            }"
            :style="{
              left: `${room.x}px`,
              top: `${room.y}px`,
              width: `${room.width}px`,
              height: `${room.height}px`,
              borderColor: getRoomColor(room.type),
              backgroundColor: `${getRoomColor(room.type)}20`,
            }"
            @mousedown="handleRoomDragStart($event, room)"
          >
            <div class="room-header">
              <span class="room-icon">{{ getRoomIcon(room.type) }}</span>
              <span class="room-name">{{ room.name }}</span>
            </div>
            <div class="room-devices">
              <span
                v-for="device in room.devices"
                :key="device.id"
                class="device-icon"
                :title="device.name"
              >
                {{ device.icon }}
              </span>
            </div>
            <button
              class="room-delete"
              @click.stop="deleteRoom(room.id)"
              title="Delete room"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>

            <!-- Resize handles -->
            <div
              class="resize-handle resize-e"
              @mousedown="handleRoomResizeStart($event, room, 'e')"
            ></div>
            <div
              class="resize-handle resize-s"
              @mousedown="handleRoomResizeStart($event, room, 's')"
            ></div>
            <div
              class="resize-handle resize-se"
              @mousedown="handleRoomResizeStart($event, room, 'se')"
            ></div>
          </div>
        </div>
      </main>

      <!-- Right Sidebar - Properties -->
      <aside class="properties-sidebar">
        <div v-if="selectedRoom" class="properties-panel">
          <h4>Room Properties</h4>

          <div class="property-group">
            <label>Name</label>
            <input
              type="text"
              class="input"
              v-model="selectedRoom.name"
            />
          </div>

          <div class="property-group">
            <label>Type</label>
            <div class="type-badge" :style="{ backgroundColor: `${getRoomColor(selectedRoom.type)}30`, color: getRoomColor(selectedRoom.type) }">
              {{ getRoomIcon(selectedRoom.type) }} {{ selectedRoom.type.replace('_', ' ') }}
            </div>
          </div>

          <div class="property-group">
            <label>Size</label>
            <div class="size-inputs">
              <input type="number" class="input" v-model.number="selectedRoom.width" min="80" max="400" /> x
              <input type="number" class="input" v-model.number="selectedRoom.height" min="60" max="300" />
            </div>
          </div>

          <div class="property-group">
            <label>Devices ({{ selectedRoom.devices.length }})</label>
            <div class="device-list">
              <div
                v-for="device in selectedRoom.devices"
                :key="device.id"
                class="device-item"
                :class="{ 'device-item-selected': selectedDevice?.id === device.id }"
                @click="selectedDevice = device"
              >
                <span class="device-icon">{{ device.icon }}</span>
                <span class="device-name">{{ device.name }}</span>
                <button
                  class="btn btn-ghost btn-icon btn-sm"
                  @click.stop="removeDeviceFromRoom(device.id, selectedRoom)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
              <p v-if="selectedRoom.devices.length === 0" class="hint">
                No devices yet. Add from the Devices tab.
              </p>
            </div>
          </div>

          <!-- Device Properties (when device selected) -->
          <div v-if="selectedDevice" class="device-properties">
            <div class="device-properties-header">
              <h5>Device Properties</h5>
              <button class="btn btn-ghost btn-icon btn-sm" @click="selectedDevice = null">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="property-group">
              <label>Device Name</label>
              <input
                type="text"
                class="input"
                v-model="selectedDevice.name"
              />
            </div>

            <div class="property-group">
              <label>Device Type</label>
              <div class="device-type-badge">
                {{ selectedDevice.icon }} {{ selectedDevice.type.replace('_', ' ') }}
              </div>
            </div>

            <div class="property-group">
              <label>Device ID</label>
              <code class="device-id">{{ selectedDevice.id }}</code>
            </div>
          </div>
        </div>

        <!-- Inhabitant Properties -->
        <div v-else-if="selectedInhabitant" class="properties-panel">
          <h4>Inhabitant Properties</h4>

          <div class="property-group">
            <label>Name</label>
            <input
              type="text"
              class="input"
              v-model="selectedInhabitant.name"
            />
          </div>

          <div class="property-group">
            <label>Role</label>
            <div class="type-badge" :style="{ backgroundColor: `${getRoleColor(selectedInhabitant.role)}20`, color: getRoleColor(selectedInhabitant.role) }">
              {{ selectedInhabitant.icon }} {{ selectedInhabitant.role }}
            </div>
          </div>

          <div class="property-group">
            <label>Age</label>
            <input
              type="number"
              class="input"
              v-model.number="selectedInhabitant.age"
              min="0"
              max="120"
            />
          </div>

          <div class="property-group">
            <label>Wake Up Time</label>
            <div class="time-input-row">
              <input
                type="range"
                class="slider"
                v-model.number="selectedInhabitant.schedule.wakeUp"
                min="0"
                max="12"
              />
              <span class="time-value">{{ formatHour(selectedInhabitant.schedule.wakeUp) }}</span>
            </div>
          </div>

          <div class="property-group">
            <label>Sleep Time</label>
            <div class="time-input-row">
              <input
                type="range"
                class="slider"
                v-model.number="selectedInhabitant.schedule.sleep"
                min="18"
                max="24"
              />
              <span class="time-value">{{ formatHour(selectedInhabitant.schedule.sleep % 24) }}</span>
            </div>
          </div>

          <div class="property-group">
            <label>Hours at Home / Day</label>
            <div class="time-input-row">
              <input
                type="range"
                class="slider"
                v-model.number="selectedInhabitant.schedule.homeTime"
                min="0"
                max="24"
              />
              <span class="time-value">{{ selectedInhabitant.schedule.homeTime }}h</span>
            </div>
          </div>

          <div class="property-group">
            <label>
              <input
                type="checkbox"
                v-model="selectedInhabitant.schedule.workFromHome"
              />
              Works from home
            </label>
          </div>

          <div class="property-group">
            <label>Preferred Devices</label>
            <div class="device-prefs">
              <span
                v-for="pref in selectedInhabitant.devicePreferences"
                :key="pref"
                class="device-pref-tag"
              >
                {{ deviceTypes.find(d => d.type === pref)?.icon || '📱' }}
                {{ pref.replace('_', ' ') }}
              </span>
            </div>
          </div>
        </div>

        <div v-else class="empty-properties">
          <p>Select a room or inhabitant to view and edit properties</p>
        </div>
      </aside>
    </div>

    <!-- Scenario Browser Modal -->
    <Teleport to="body">
      <div v-if="showScenarioBrowser" class="modal-overlay" @click.self="showScenarioBrowser = false">
        <div class="modal-container scenario-browser-modal">
          <ScenarioBrowser
            mode="home"
            :show-preview="true"
            @load="loadPreloadedScenario"
            @close="showScenarioBrowser = false"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.home-builder {
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

.header-actions .btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.header-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
  margin: 0 var(--spacing-xs);
}

/* Sync button styles */
.sync-btn.btn-success {
  background: #10b981;
  color: white;
  border-color: #10b981;
}

.sync-btn.btn-success:hover {
  background: #059669;
}

.sync-btn.btn-danger {
  background: #ef4444;
  color: white;
  border-color: #ef4444;
}

.sync-btn.btn-danger:hover {
  background: #dc2626;
}

.sync-btn .spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.builder-content {
  display: grid;
  grid-template-columns: 240px 1fr 280px;
  gap: var(--spacing-md);
  flex: 1;
  overflow: hidden;
}

/* Palette Sidebar */
.palette-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.palette-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
}

.tab {
  flex: 1;
  padding: var(--spacing-sm);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.tab.active {
  color: var(--color-primary);
  background: var(--bg-hover);
  border-bottom: 2px solid var(--color-primary);
}

.palette-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.palette-section {
  margin-bottom: var(--spacing-md);
}

.palette-section h4 {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.section-description {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
  line-height: 1.4;
  letter-spacing: 0.5px;
}

.palette-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-xs);
}

.palette-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.palette-item:hover {
  border-color: var(--color-primary);
  background: var(--bg-hover);
}

.item-icon {
  font-size: 1.25rem;
  margin-bottom: 2px;
}

.item-label {
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-align: center;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.template-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.template-item:hover {
  border-color: var(--color-primary);
}

.template-icon {
  font-size: 1.5rem;
}

.template-info {
  display: flex;
  flex-direction: column;
}

.template-name {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
}

.template-desc {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-style: italic;
}

/* Device Category Tabs */
.device-category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: var(--spacing-xs);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  max-height: 120px;
  overflow-y: auto;
}

.category-tab {
  padding: 4px 8px;
  font-size: 0.65rem;
  font-weight: 500;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  color: var(--text-secondary);
  white-space: nowrap;
}

.category-tab:hover {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.category-tab.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

/* Canvas Area */
.canvas-area {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
}

.canvas {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: auto;
  background-color: var(--bg-input);
}

.canvas.show-grid {
  background-image:
    linear-gradient(to right, var(--border-color) 1px, transparent 1px),
    linear-gradient(to bottom, var(--border-color) 1px, transparent 1px);
}

.empty-canvas {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: var(--spacing-md);
}

.empty-canvas h3 {
  margin-bottom: var(--spacing-sm);
  color: var(--text-primary);
}

.empty-canvas p {
  font-size: 0.875rem;
}

/* Room */
.room {
  position: absolute;
  border: 2px solid;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: box-shadow var(--transition-fast);
  padding: var(--spacing-xs);
}

.room:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.room.selected {
  box-shadow: 0 0 0 3px var(--color-primary);
}

.room-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
}

.room-icon {
  font-size: 0.875rem;
}

.room-name {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-devices {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.room-devices .device-icon {
  font-size: 0.75rem;
}

.room-delete {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  background: var(--color-error);
  color: white;
  border: none;
  border-radius: 50%;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.room:hover .room-delete {
  display: flex;
}

/* Drag and resize states */
.canvas.dragging {
  cursor: grabbing;
}

.room.dragging {
  opacity: 0.8;
  z-index: 100;
  cursor: grabbing;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.room.resizing {
  z-index: 100;
}

.room {
  cursor: grab;
}

.room:active {
  cursor: grabbing;
}

/* Resize handles */
.resize-handle {
  position: absolute;
  background: transparent;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.room:hover .resize-handle,
.room.selected .resize-handle {
  opacity: 1;
}

.resize-e {
  right: -4px;
  top: 10%;
  bottom: 10%;
  width: 8px;
  cursor: ew-resize;
}

.resize-s {
  bottom: -4px;
  left: 10%;
  right: 10%;
  height: 8px;
  cursor: ns-resize;
}

.resize-se {
  right: -6px;
  bottom: -6px;
  width: 12px;
  height: 12px;
  cursor: nwse-resize;
  background: var(--color-primary);
  border-radius: 2px;
}

.room:hover .resize-se,
.room.selected .resize-se {
  opacity: 0.7;
}

.resize-se:hover {
  opacity: 1 !important;
}

/* Properties Sidebar */
.properties-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
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

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
}

.size-inputs {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.size-inputs .input {
  width: 60px;
  min-width: 60px;
  text-align: center;
  padding: var(--spacing-xs) var(--spacing-xs);
  font-size: 0.85rem;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 200px;
  overflow-y: auto;
}

.device-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.device-item .device-icon {
  font-size: 1rem;
}

.device-item .device-name {
  flex: 1;
  font-size: 0.8rem;
}

.device-item-selected {
  background: var(--color-primary-light, rgba(59, 130, 246, 0.15));
  border: 1px solid var(--color-primary);
}

.device-item:hover {
  background: var(--bg-hover);
  cursor: pointer;
}

/* Device Properties Panel */
.device-properties {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.device-properties-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.device-properties-header h5 {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.device-type-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
  color: var(--text-secondary);
}

.device-id {
  display: block;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  color: var(--text-muted);
  word-break: break-all;
  font-family: monospace;
}

.empty-properties {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--text-muted);
}

/* Inhabitant Styles */
.inhabitant-template-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.inhabitant-template-item {
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
  transition: all var(--transition-fast);
}

.inhabitant-template-item:hover {
  border-color: var(--color-primary);
}

.inhabitant-template-item .template-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 1.1rem;
}

.current-inhabitants-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  max-height: 180px;
  overflow-y: auto;
}

.current-inhabitant-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.current-inhabitant-item:hover {
  background: var(--bg-hover);
}

.current-inhabitant-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light, rgba(59, 130, 246, 0.1));
}

.inhabitant-icon {
  font-size: 1.25rem;
}

.inhabitant-info {
  flex: 1;
  min-width: 0;
}

.inhabitant-name {
  display: block;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
}

.inhabitant-role {
  display: block;
  font-size: 0.65rem;
  text-transform: capitalize;
}

/* Inhabitant properties */
.time-input-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.time-input-row .slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-input);
  outline: none;
}

.time-input-row .slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
}

.time-input-row .slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: none;
}

.time-value {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 60px;
  text-align: right;
}

.device-prefs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.device-pref-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

/* Modal Styles */
.modal-overlay {
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
  padding: var(--spacing-lg);
}

.modal-container {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  max-width: 90vw;
  max-height: 90vh;
  width: 1200px;
  overflow: hidden;
}

.scenario-browser-modal {
  height: 75vh;
}

/* Responsive */
@media (max-width: 1024px) {
  .builder-content {
    grid-template-columns: 200px 1fr;
  }

  .properties-sidebar {
    display: none;
  }
}

@media (max-width: 768px) {
  .builder-content {
    grid-template-columns: 1fr;
  }

  .palette-sidebar {
    display: none;
  }
}
</style>
