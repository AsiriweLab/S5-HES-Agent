<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  scenarioManager,
  categoryInfo,
  difficultyInfo,
  type ThreatScenario,
  type HomeScenario,
  type ScenarioCategory,
  type DifficultyLevel,
} from '@/services/PreloadedScenarioManager'

// Props
const props = defineProps<{
  mode: 'threat' | 'home' | 'combined'
  showPreview?: boolean
}>()

// Emits
const emit = defineEmits<{
  (e: 'select', scenario: ThreatScenario | HomeScenario): void
  (e: 'load', scenario: ThreatScenario | HomeScenario): void
  (e: 'close'): void
}>()

// State
const searchQuery = ref('')
const selectedCategory = ref<ScenarioCategory | 'all'>('all')
const selectedDifficulty = ref<DifficultyLevel | 'all'>('all')
const selectedScenario = ref<ThreatScenario | HomeScenario | null>(null)
const viewMode = ref<'grid' | 'list'>('grid')

// Initialize manager on mount
onMounted(async () => {
  await scenarioManager.initialize()
})

// Computed
const threatScenarios = computed(() => {
  let scenarios = scenarioManager.getAllThreatScenarios()

  // Filter by category
  if (selectedCategory.value !== 'all') {
    scenarios = scenarios.filter(s => s.category === selectedCategory.value)
  }

  // Filter by difficulty
  if (selectedDifficulty.value !== 'all') {
    scenarios = scenarios.filter(s => s.difficulty === selectedDifficulty.value)
  }

  // Filter by search query
  if (searchQuery.value) {
    scenarios = scenarioManager.searchThreatScenarios(searchQuery.value)
  }

  return scenarios
})

const homeScenarios = computed(() => {
  let scenarios = scenarioManager.getAllHomeScenarios()

  // Filter by search query
  if (searchQuery.value) {
    scenarios = scenarioManager.searchHomeScenarios(searchQuery.value)
  }

  return scenarios
})

const displayScenarios = computed(() => {
  if (props.mode === 'threat') return threatScenarios.value
  if (props.mode === 'home') return homeScenarios.value
  return []
})

const categoryCounts = computed(() => scenarioManager.getThreatCategoryCounts())
const difficultyCounts = computed(() => scenarioManager.getThreatDifficultyCounts())

const categories = computed(() => {
  return Object.entries(categoryInfo).map(([key, value]) => ({
    id: key as ScenarioCategory,
    ...value,
    count: categoryCounts.value[key as ScenarioCategory] || 0,
  }))
})

const difficulties = computed(() => {
  return Object.entries(difficultyInfo).map(([key, value]) => ({
    id: key as DifficultyLevel,
    ...value,
    count: difficultyCounts.value[key as DifficultyLevel] || 0,
  }))
})

// Methods
function selectScenario(scenario: ThreatScenario | HomeScenario) {
  selectedScenario.value = scenario
  emit('select', scenario)
}

function loadScenario() {
  if (selectedScenario.value) {
    emit('load', selectedScenario.value)
  }
}

function clearFilters() {
  searchQuery.value = ''
  selectedCategory.value = 'all'
  selectedDifficulty.value = 'all'
}

function getDifficultyColor(difficulty: DifficultyLevel): string {
  return difficultyInfo[difficulty]?.color || '#6b7280'
}

function getCategoryColor(category: ScenarioCategory): string {
  return categoryInfo[category]?.color || '#6b7280'
}

function getCategoryIcon(category: ScenarioCategory): string {
  return categoryInfo[category]?.icon || '📁'
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
}

function isThreatScenario(scenario: ThreatScenario | HomeScenario): scenario is ThreatScenario {
  return 'events' in scenario && 'category' in scenario
}
</script>

<template>
  <div class="scenario-browser">
    <!-- Header -->
    <div class="browser-header">
      <div class="header-title">
        <h3>
          {{ mode === 'threat' ? 'Threat Scenarios' : mode === 'home' ? 'Home Configurations' : 'Combined Scenarios' }}
        </h3>
        <span class="scenario-count">{{ displayScenarios.length }} available</span>
      </div>
      <div class="header-actions">
        <div class="view-toggle">
          <button
            :class="['toggle-btn', { active: viewMode === 'grid' }]"
            @click="viewMode = 'grid'"
            title="Grid view"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="7" height="7"></rect>
              <rect x="14" y="3" width="7" height="7"></rect>
              <rect x="3" y="14" width="7" height="7"></rect>
              <rect x="14" y="14" width="7" height="7"></rect>
            </svg>
          </button>
          <button
            :class="['toggle-btn', { active: viewMode === 'list' }]"
            @click="viewMode = 'list'"
            title="List view"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="8" y1="6" x2="21" y2="6"></line>
              <line x1="8" y1="12" x2="21" y2="12"></line>
              <line x1="8" y1="18" x2="21" y2="18"></line>
              <line x1="3" y1="6" x2="3.01" y2="6"></line>
              <line x1="3" y1="12" x2="3.01" y2="12"></line>
              <line x1="3" y1="18" x2="3.01" y2="18"></line>
            </svg>
          </button>
        </div>
        <button class="btn btn-ghost btn-icon" @click="emit('close')" title="Close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <div class="browser-content">
      <!-- Sidebar Filters -->
      <aside class="filter-sidebar">
        <!-- Search -->
        <div class="filter-section">
          <label>Search</label>
          <div class="search-input">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              v-model="searchQuery"
              placeholder="Search scenarios..."
            />
          </div>
        </div>

        <!-- Category Filter (for threat mode) -->
        <div v-if="mode === 'threat'" class="filter-section">
          <div class="filter-header">
            <label>Category</label>
            <button
              v-if="selectedCategory !== 'all'"
              class="clear-filter"
              @click="selectedCategory = 'all'"
            >
              Clear
            </button>
          </div>
          <div class="filter-list">
            <button
              :class="['filter-item', { active: selectedCategory === 'all' }]"
              @click="selectedCategory = 'all'"
            >
              <span class="filter-icon">📁</span>
              <span class="filter-name">All Categories</span>
              <span class="filter-count">{{ threatScenarios.length }}</span>
            </button>
            <button
              v-for="cat in categories"
              :key="cat.id"
              :class="['filter-item', { active: selectedCategory === cat.id }]"
              @click="selectedCategory = cat.id"
            >
              <span class="filter-icon">{{ cat.icon }}</span>
              <span class="filter-name">{{ cat.name }}</span>
              <span class="filter-count">{{ cat.count }}</span>
            </button>
          </div>
        </div>

        <!-- Difficulty Filter -->
        <div v-if="mode === 'threat'" class="filter-section">
          <div class="filter-header">
            <label>Difficulty</label>
            <button
              v-if="selectedDifficulty !== 'all'"
              class="clear-filter"
              @click="selectedDifficulty = 'all'"
            >
              Clear
            </button>
          </div>
          <div class="filter-list">
            <button
              :class="['filter-item', { active: selectedDifficulty === 'all' }]"
              @click="selectedDifficulty = 'all'"
            >
              <span class="filter-dot" style="background: #6b7280"></span>
              <span class="filter-name">All Levels</span>
            </button>
            <button
              v-for="diff in difficulties"
              :key="diff.id"
              :class="['filter-item', { active: selectedDifficulty === diff.id }]"
              @click="selectedDifficulty = diff.id"
            >
              <span class="filter-dot" :style="{ background: diff.color }"></span>
              <span class="filter-name">{{ diff.name }}</span>
              <span class="filter-count">{{ diff.count }}</span>
            </button>
          </div>
        </div>

        <button
          v-if="searchQuery || selectedCategory !== 'all' || selectedDifficulty !== 'all'"
          class="btn btn-ghost btn-sm clear-all-btn"
          @click="clearFilters"
        >
          Clear All Filters
        </button>
      </aside>

      <!-- Scenario Grid/List -->
      <main class="scenario-list">
        <!-- Empty State -->
        <div v-if="displayScenarios.length === 0" class="empty-state">
          <div class="empty-icon">📭</div>
          <h4>No Scenarios Found</h4>
          <p v-if="searchQuery || selectedCategory !== 'all' || selectedDifficulty !== 'all'">
            Try adjusting your filters or search query
          </p>
          <p v-else>
            No preloaded scenarios available yet. Create your own scenarios using the builder!
          </p>
        </div>

        <!-- Grid View -->
        <div v-else-if="viewMode === 'grid'" class="scenario-grid">
          <div
            v-for="scenario in displayScenarios"
            :key="scenario.id"
            :class="['scenario-card', { selected: selectedScenario?.id === scenario.id }]"
            @click="selectScenario(scenario)"
          >
            <div class="card-header">
              <span
                v-if="isThreatScenario(scenario)"
                class="category-badge"
                :style="{ backgroundColor: `${getCategoryColor(scenario.category)}20`, color: getCategoryColor(scenario.category) }"
              >
                {{ getCategoryIcon(scenario.category) }} {{ categoryInfo[scenario.category]?.name }}
              </span>
              <span
                v-if="isThreatScenario(scenario)"
                class="difficulty-badge"
                :style="{ backgroundColor: `${getDifficultyColor(scenario.difficulty)}20`, color: getDifficultyColor(scenario.difficulty) }"
              >
                {{ difficultyInfo[scenario.difficulty]?.name }}
              </span>
            </div>
            <h4 class="card-title">{{ scenario.name }}</h4>
            <p class="card-description">{{ scenario.description }}</p>
            <div class="card-meta">
              <span v-if="isThreatScenario(scenario)" class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                {{ formatDuration(scenario.estimatedDuration) }}
              </span>
              <span v-if="isThreatScenario(scenario)" class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                {{ scenario.events.length }} events
              </span>
              <span v-if="!isThreatScenario(scenario)" class="meta-item">
                {{ scenario.rooms.length }} rooms
              </span>
            </div>
            <div v-if="scenario.tags && scenario.tags.length > 0" class="card-tags">
              <span v-for="tag in scenario.tags.slice(0, 3)" :key="tag" class="tag">
                {{ tag }}
              </span>
              <span v-if="scenario.tags.length > 3" class="tag more">
                +{{ scenario.tags.length - 3 }}
              </span>
            </div>
          </div>
        </div>

        <!-- List View -->
        <div v-else class="scenario-table">
          <div class="table-header">
            <span class="col-name">Name</span>
            <span v-if="mode === 'threat'" class="col-category">Category</span>
            <span v-if="mode === 'threat'" class="col-difficulty">Difficulty</span>
            <span class="col-details">Details</span>
          </div>
          <div
            v-for="scenario in displayScenarios"
            :key="scenario.id"
            :class="['table-row', { selected: selectedScenario?.id === scenario.id }]"
            @click="selectScenario(scenario)"
          >
            <span class="col-name">
              <strong>{{ scenario.name }}</strong>
              <small>{{ scenario.description }}</small>
            </span>
            <span v-if="isThreatScenario(scenario)" class="col-category">
              <span
                class="category-badge small"
                :style="{ backgroundColor: `${getCategoryColor(scenario.category)}20`, color: getCategoryColor(scenario.category) }"
              >
                {{ getCategoryIcon(scenario.category) }}
              </span>
            </span>
            <span v-if="isThreatScenario(scenario)" class="col-difficulty">
              <span
                class="difficulty-dot"
                :style="{ backgroundColor: getDifficultyColor(scenario.difficulty) }"
              ></span>
              {{ difficultyInfo[scenario.difficulty]?.name }}
            </span>
            <span class="col-details">
              <template v-if="isThreatScenario(scenario)">
                {{ scenario.events.length }} events, {{ formatDuration(scenario.estimatedDuration) }}
              </template>
              <template v-else>
                {{ scenario.rooms.length }} rooms
              </template>
            </span>
          </div>
        </div>
      </main>

      <!-- Preview Panel -->
      <aside v-if="showPreview && selectedScenario" class="preview-panel">
        <div class="preview-header">
          <h4>Preview</h4>
        </div>
        <div class="preview-content">
          <h3>{{ selectedScenario.name }}</h3>
          <p class="preview-description">{{ selectedScenario.description }}</p>

          <template v-if="isThreatScenario(selectedScenario)">
            <div class="preview-meta">
              <div class="meta-row">
                <span class="meta-label">Category</span>
                <span
                  class="category-badge"
                  :style="{ backgroundColor: `${getCategoryColor(selectedScenario.category)}20`, color: getCategoryColor(selectedScenario.category) }"
                >
                  {{ getCategoryIcon(selectedScenario.category) }} {{ categoryInfo[selectedScenario.category]?.name }}
                </span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Difficulty</span>
                <span
                  class="difficulty-badge"
                  :style="{ backgroundColor: `${getDifficultyColor(selectedScenario.difficulty)}20`, color: getDifficultyColor(selectedScenario.difficulty) }"
                >
                  {{ difficultyInfo[selectedScenario.difficulty]?.name }}
                </span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Duration</span>
                <span>{{ formatDuration(selectedScenario.estimatedDuration) }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Events</span>
                <span>{{ selectedScenario.events.length }}</span>
              </div>
            </div>

            <div v-if="selectedScenario.learningObjectives?.length" class="preview-section">
              <h5>Learning Objectives</h5>
              <ul>
                <li v-for="(obj, i) in selectedScenario.learningObjectives" :key="i">
                  {{ obj }}
                </li>
              </ul>
            </div>

            <div v-if="selectedScenario.mitreTechniques?.length" class="preview-section">
              <h5>MITRE ATT&CK Techniques</h5>
              <div class="mitre-tags">
                <span v-for="tech in selectedScenario.mitreTechniques" :key="tech" class="mitre-tag">
                  {{ tech }}
                </span>
              </div>
            </div>
          </template>

          <button class="btn btn-primary load-btn" @click="loadScenario">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            Load Scenario
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.scenario-browser {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.browser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.header-title h3 {
  margin: 0;
  font-size: 1.1rem;
}

.scenario-count {
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--bg-input);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.view-toggle {
  display: flex;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  padding: 2px;
}

.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toggle-btn:hover {
  color: var(--text-primary);
}

.toggle-btn.active {
  background: var(--bg-card);
  color: var(--color-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.browser-content {
  display: grid;
  grid-template-columns: 220px 1fr 280px;
  flex: 1;
  overflow: hidden;
}

.browser-content:not(:has(.preview-panel)) {
  grid-template-columns: 220px 1fr;
}

/* Filter Sidebar */
.filter-sidebar {
  padding: var(--spacing-md);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
}

.filter-section {
  margin-bottom: var(--spacing-lg);
}

.filter-section label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: var(--spacing-sm);
}

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.filter-header label {
  margin: 0;
}

.clear-filter {
  font-size: 0.7rem;
  color: var(--color-primary);
  background: none;
  border: none;
  cursor: pointer;
}

.search-input {
  position: relative;
}

.search-input svg {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}

.search-input input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-sm) var(--spacing-sm) 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.search-input input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.filter-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-xs) var(--spacing-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8rem;
  text-align: left;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.filter-item.active {
  background: var(--color-primary-light, rgba(59, 130, 246, 0.1));
  color: var(--color-primary);
}

.filter-icon {
  font-size: 1rem;
}

.filter-name {
  flex: 1;
}

.filter-count {
  font-size: 0.7rem;
  color: var(--text-muted);
  background: var(--bg-input);
  padding: 1px 6px;
  border-radius: 10px;
}

.filter-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.clear-all-btn {
  width: 100%;
  margin-top: var(--spacing-md);
}

/* Scenario List */
.scenario-list {
  padding: var(--spacing-md);
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.empty-state h4 {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-primary);
}

.empty-state p {
  margin: 0;
  max-width: 300px;
}

/* Grid View */
.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--spacing-md);
}

.scenario-card {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.scenario-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.scenario-card.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light, rgba(59, 130, 246, 0.05));
}

.card-header {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
}

.category-badge,
.difficulty-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-weight: 500;
}

.category-badge.small {
  padding: 4px 6px;
}

.card-title {
  margin: 0 0 var(--spacing-xs);
  font-size: 0.95rem;
  color: var(--text-primary);
}

.card-description {
  margin: 0 0 var(--spacing-sm);
  font-size: 0.8rem;
  color: var(--text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  gap: var(--spacing-md);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: var(--spacing-sm);
}

.tag {
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-xs);
  font-size: 0.65rem;
  color: var(--text-muted);
}

.tag.more {
  font-weight: 500;
  color: var(--text-secondary);
}

/* List View */
.scenario-table {
  display: flex;
  flex-direction: column;
}

.table-header {
  display: grid;
  grid-template-columns: 1fr 120px 100px 150px;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr 120px 100px 150px;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.table-row:hover {
  background: var(--bg-hover);
}

.table-row.selected {
  background: var(--color-primary-light, rgba(59, 130, 246, 0.05));
}

.col-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.col-name strong {
  font-size: 0.85rem;
  color: var(--text-primary);
}

.col-name small {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-category,
.col-difficulty,
.col-details {
  display: flex;
  align-items: center;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.difficulty-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

/* Preview Panel */
.preview-panel {
  border-left: 1px solid var(--border-color);
  overflow-y: auto;
}

.preview-header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.preview-header h4 {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.preview-content {
  padding: var(--spacing-md);
}

.preview-content h3 {
  margin: 0 0 var(--spacing-sm);
  font-size: 1rem;
  color: var(--text-primary);
}

.preview-description {
  margin: 0 0 var(--spacing-md);
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.preview-meta {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}

.meta-label {
  color: var(--text-muted);
}

.preview-section {
  margin-bottom: var(--spacing-md);
}

.preview-section h5 {
  margin: 0 0 var(--spacing-sm);
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.preview-section ul {
  margin: 0;
  padding-left: var(--spacing-md);
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.preview-section li {
  margin-bottom: 4px;
}

.mitre-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mitre-tag {
  padding: 2px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--text-secondary);
}

.load-btn {
  width: 100%;
  margin-top: var(--spacing-md);
}

/* Responsive */
@media (max-width: 1024px) {
  .browser-content {
    grid-template-columns: 180px 1fr;
  }

  .preview-panel {
    display: none;
  }
}

@media (max-width: 768px) {
  .browser-content {
    grid-template-columns: 1fr;
  }

  .filter-sidebar {
    display: none;
  }
}
</style>
