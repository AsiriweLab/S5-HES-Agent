/**
 * PreloadedScenarioManager - Service for managing preloaded threat and home scenarios
 * Provides scenario templates, categories, and loading utilities
 */

// ============== TYPES ==============

export type ScenarioCategory =
  | 'reconnaissance'
  | 'initial_access'
  | 'persistence'
  | 'privilege_escalation'
  | 'defense_evasion'
  | 'credential_access'
  | 'discovery'
  | 'lateral_movement'
  | 'collection'
  | 'exfiltration'
  | 'impact'

export type DifficultyLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert'

export type HomeType = 'apartment' | 'house' | 'smart_home' | 'enterprise' | 'industrial'

export interface ScenarioMetadata {
  id: string
  name: string
  description: string
  category: ScenarioCategory
  difficulty: DifficultyLevel
  estimatedDuration: number // minutes
  tags: string[]
  mitreTechniques: string[]
  prerequisites: string[]
  learningObjectives: string[]
  createdAt: string
  version: string
}

export interface ThreatEvent {
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
}

export interface ThreatScenario extends ScenarioMetadata {
  events: ThreatEvent[]
  simulationDuration: number
  targetHomeType: HomeType
  attackChainDescription: string
}

export interface Device {
  id: string
  name: string
  type: string
  icon: string
  x: number
  y: number
}

export interface Room {
  id: string
  name: string
  type: string
  x: number
  y: number
  width: number
  height: number
  devices: Device[]
}

export interface Inhabitant {
  id: string
  name: string
  role: string
  icon: string
  age: number
  schedule: {
    wakeUp: number
    sleep: number
    homeTime: number
    workFromHome: boolean
    activeHours: number[]
  }
  devicePreferences: string[]
}

export interface HomeScenario {
  id: string
  name: string
  description: string
  homeType: HomeType
  rooms: Room[]
  inhabitants: Inhabitant[]
  tags: string[]
  securityLevel: 'low' | 'medium' | 'high'
  createdAt: string
}

export interface CombinedScenario {
  id: string
  name: string
  description: string
  home: HomeScenario
  threats: ThreatScenario
  difficulty: DifficultyLevel
  tags: string[]
}

// ============== CATEGORY METADATA ==============

export const categoryInfo: Record<ScenarioCategory, { name: string; description: string; icon: string; color: string }> = {
  reconnaissance: {
    name: 'Reconnaissance',
    description: 'Gathering information about target systems',
    icon: '🔍',
    color: '#6366f1',
  },
  initial_access: {
    name: 'Initial Access',
    description: 'Gaining entry to the target network',
    icon: '🚪',
    color: '#ef4444',
  },
  persistence: {
    name: 'Persistence',
    description: 'Maintaining access to compromised systems',
    icon: '🔗',
    color: '#f97316',
  },
  privilege_escalation: {
    name: 'Privilege Escalation',
    description: 'Gaining higher-level permissions',
    icon: '⬆️',
    color: '#eab308',
  },
  defense_evasion: {
    name: 'Defense Evasion',
    description: 'Avoiding detection by security systems',
    icon: '🥷',
    color: '#84cc16',
  },
  credential_access: {
    name: 'Credential Access',
    description: 'Stealing account credentials',
    icon: '🔑',
    color: '#ec4899',
  },
  discovery: {
    name: 'Discovery',
    description: 'Exploring the environment and finding targets',
    icon: '🗺️',
    color: '#14b8a6',
  },
  lateral_movement: {
    name: 'Lateral Movement',
    description: 'Moving through the network to other systems',
    icon: '↔️',
    color: '#8b5cf6',
  },
  collection: {
    name: 'Collection',
    description: 'Gathering data of interest',
    icon: '📦',
    color: '#06b6d4',
  },
  exfiltration: {
    name: 'Exfiltration',
    description: 'Stealing data from the network',
    icon: '📤',
    color: '#dc2626',
  },
  impact: {
    name: 'Impact',
    description: 'Disrupting operations or destroying data',
    icon: '💥',
    color: '#7c3aed',
  },
}

export const difficultyInfo: Record<DifficultyLevel, { name: string; description: string; color: string }> = {
  beginner: {
    name: 'Beginner',
    description: 'Basic attacks with simple techniques',
    color: '#22c55e',
  },
  intermediate: {
    name: 'Intermediate',
    description: 'Moderate complexity requiring some skill',
    color: '#eab308',
  },
  advanced: {
    name: 'Advanced',
    description: 'Complex multi-stage attacks',
    color: '#f97316',
  },
  expert: {
    name: 'Expert',
    description: 'Sophisticated APT-level scenarios',
    color: '#dc2626',
  },
}

// ============== SCENARIO MANAGER CLASS ==============

class PreloadedScenarioManager {
  private threatScenarios: ThreatScenario[] = []
  private homeScenarios: HomeScenario[] = []
  private combinedScenarios: CombinedScenario[] = []
  private initialized = false

  /**
   * Initialize the manager with preloaded scenarios
   */
  async initialize(): Promise<void> {
    if (this.initialized) return

    // Load built-in scenarios
    this.loadBuiltInScenarios()
    this.initialized = true
  }

  /**
   * Load built-in scenarios (called during initialization)
   */
  private loadBuiltInScenarios(): void {
    // Import preloaded scenarios
    import('@/data/preloadedScenarios').then(({ preloadedThreatScenarios, preloadedHomeScenarios }) => {
      this.threatScenarios = [...preloadedThreatScenarios]
      this.homeScenarios = [...preloadedHomeScenarios]
      this.combinedScenarios = []
    }).catch(err => {
      console.warn('Failed to load preloaded scenarios:', err)
      this.threatScenarios = []
      this.homeScenarios = []
      this.combinedScenarios = []
    })
  }

  /**
   * Register a new threat scenario
   */
  registerThreatScenario(scenario: ThreatScenario): void {
    const existing = this.threatScenarios.findIndex(s => s.id === scenario.id)
    if (existing >= 0) {
      this.threatScenarios[existing] = scenario
    } else {
      this.threatScenarios.push(scenario)
    }
  }

  /**
   * Register a new home scenario
   */
  registerHomeScenario(scenario: HomeScenario): void {
    const existing = this.homeScenarios.findIndex(s => s.id === scenario.id)
    if (existing >= 0) {
      this.homeScenarios[existing] = scenario
    } else {
      this.homeScenarios.push(scenario)
    }
  }

  /**
   * Register a combined scenario
   */
  registerCombinedScenario(scenario: CombinedScenario): void {
    const existing = this.combinedScenarios.findIndex(s => s.id === scenario.id)
    if (existing >= 0) {
      this.combinedScenarios[existing] = scenario
    } else {
      this.combinedScenarios.push(scenario)
    }
  }

  // ============== GETTERS ==============

  /**
   * Get all threat scenarios
   */
  getAllThreatScenarios(): ThreatScenario[] {
    return [...this.threatScenarios]
  }

  /**
   * Get all home scenarios
   */
  getAllHomeScenarios(): HomeScenario[] {
    return [...this.homeScenarios]
  }

  /**
   * Get all combined scenarios
   */
  getAllCombinedScenarios(): CombinedScenario[] {
    return [...this.combinedScenarios]
  }

  /**
   * Get a threat scenario by ID
   */
  getThreatScenarioById(id: string): ThreatScenario | undefined {
    return this.threatScenarios.find(s => s.id === id)
  }

  /**
   * Get a home scenario by ID
   */
  getHomeScenarioById(id: string): HomeScenario | undefined {
    return this.homeScenarios.find(s => s.id === id)
  }

  /**
   * Get a combined scenario by ID
   */
  getCombinedScenarioById(id: string): CombinedScenario | undefined {
    return this.combinedScenarios.find(s => s.id === id)
  }

  // ============== FILTERS ==============

  /**
   * Filter threat scenarios by category
   */
  getThreatScenariosByCategory(category: ScenarioCategory): ThreatScenario[] {
    return this.threatScenarios.filter(s => s.category === category)
  }

  /**
   * Filter threat scenarios by difficulty
   */
  getThreatScenariosByDifficulty(difficulty: DifficultyLevel): ThreatScenario[] {
    return this.threatScenarios.filter(s => s.difficulty === difficulty)
  }

  /**
   * Filter threat scenarios by tags
   */
  getThreatScenariosByTags(tags: string[]): ThreatScenario[] {
    return this.threatScenarios.filter(s =>
      tags.some(tag => s.tags.includes(tag))
    )
  }

  /**
   * Filter threat scenarios by home type
   */
  getThreatScenariosByHomeType(homeType: HomeType): ThreatScenario[] {
    return this.threatScenarios.filter(s => s.targetHomeType === homeType)
  }

  /**
   * Filter home scenarios by type
   */
  getHomeScenariosByType(homeType: HomeType): HomeScenario[] {
    return this.homeScenarios.filter(s => s.homeType === homeType)
  }

  /**
   * Filter home scenarios by security level
   */
  getHomeScenariosBySecurityLevel(level: 'low' | 'medium' | 'high'): HomeScenario[] {
    return this.homeScenarios.filter(s => s.securityLevel === level)
  }

  /**
   * Search scenarios by text query
   */
  searchThreatScenarios(query: string): ThreatScenario[] {
    const lowerQuery = query.toLowerCase()
    return this.threatScenarios.filter(s =>
      s.name.toLowerCase().includes(lowerQuery) ||
      s.description.toLowerCase().includes(lowerQuery) ||
      s.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
    )
  }

  /**
   * Search home scenarios by text query
   */
  searchHomeScenarios(query: string): HomeScenario[] {
    const lowerQuery = query.toLowerCase()
    return this.homeScenarios.filter(s =>
      s.name.toLowerCase().includes(lowerQuery) ||
      s.description.toLowerCase().includes(lowerQuery) ||
      s.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
    )
  }

  // ============== STATISTICS ==============

  /**
   * Get category counts for threat scenarios
   */
  getThreatCategoryCounts(): Record<ScenarioCategory, number> {
    const counts: Record<ScenarioCategory, number> = {
      reconnaissance: 0,
      initial_access: 0,
      persistence: 0,
      privilege_escalation: 0,
      defense_evasion: 0,
      credential_access: 0,
      discovery: 0,
      lateral_movement: 0,
      collection: 0,
      exfiltration: 0,
      impact: 0,
    }
    this.threatScenarios.forEach(s => {
      counts[s.category]++
    })
    return counts
  }

  /**
   * Get difficulty counts for threat scenarios
   */
  getThreatDifficultyCounts(): Record<DifficultyLevel, number> {
    const counts: Record<DifficultyLevel, number> = {
      beginner: 0,
      intermediate: 0,
      advanced: 0,
      expert: 0,
    }
    this.threatScenarios.forEach(s => {
      counts[s.difficulty]++
    })
    return counts
  }

  /**
   * Get all unique tags from threat scenarios
   */
  getAllThreatTags(): string[] {
    const tags = new Set<string>()
    this.threatScenarios.forEach(s => {
      s.tags.forEach(tag => tags.add(tag))
    })
    return Array.from(tags).sort()
  }

  /**
   * Get all unique MITRE techniques from threat scenarios
   */
  getAllMitreTechniques(): string[] {
    const techniques = new Set<string>()
    this.threatScenarios.forEach(s => {
      s.mitreTechniques.forEach(tech => techniques.add(tech))
    })
    return Array.from(techniques).sort()
  }

  // ============== IMPORT/EXPORT ==============

  /**
   * Export a threat scenario to JSON
   */
  exportThreatScenario(id: string): string | null {
    const scenario = this.getThreatScenarioById(id)
    if (!scenario) return null
    return JSON.stringify(scenario, null, 2)
  }

  /**
   * Export a home scenario to JSON
   */
  exportHomeScenario(id: string): string | null {
    const scenario = this.getHomeScenarioById(id)
    if (!scenario) return null
    return JSON.stringify(scenario, null, 2)
  }

  /**
   * Import a threat scenario from JSON
   */
  importThreatScenario(json: string): ThreatScenario | null {
    try {
      const scenario = JSON.parse(json) as ThreatScenario
      // Validate required fields
      if (!scenario.id || !scenario.name || !scenario.events) {
        return null
      }
      this.registerThreatScenario(scenario)
      return scenario
    } catch {
      return null
    }
  }

  /**
   * Import a home scenario from JSON
   */
  importHomeScenario(json: string): HomeScenario | null {
    try {
      const scenario = JSON.parse(json) as HomeScenario
      // Validate required fields
      if (!scenario.id || !scenario.name || !scenario.rooms) {
        return null
      }
      this.registerHomeScenario(scenario)
      return scenario
    } catch {
      return null
    }
  }
}

// Export singleton instance
export const scenarioManager = new PreloadedScenarioManager()

// Export class for testing
export { PreloadedScenarioManager }
