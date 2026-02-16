<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const API_BASE = 'http://localhost:8000/api/exports'

// Types
interface ExportTemplate {
  template_id: string
  name: string
  description: string
  publication_format: string
  export_format: string
  figure_dpi: number
  column_count: number
}

interface WizardState {
  wizard_id: string
  current_step: string
  template: string | null
  publication_format: string | null
  export_format: string | null
  title: string
  authors: string[]
  include_tables: boolean
  include_figures: boolean
  include_methodology: boolean
  include_citations: boolean
  table_count: number
  figure_count: number
  citation_count: number
}

interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

interface PreviewResult {
  success: boolean
  content: string
  format: string
  word_count: number
  table_count: number
  figure_count: number
}

interface PlotResult {
  success: boolean
  output_path: string
  format: string
  file_size_bytes: number
  base64_data: string
  plot_id: string
}

interface ExportStatus {
  publication_exporter: boolean
  plot_generator: boolean
  missing_plot_dependencies: string[]
  jupyter_integration: boolean
  export_wizard: boolean
  available_templates: string[]
  available_formats: {
    publication: string[]
    export: string[]
    plot: string[]
  }
}

// State
const isLoading = ref(false)
const error = ref<string | null>(null)
const status = ref<ExportStatus | null>(null)
const templates = ref<ExportTemplate[]>([])
const wizardState = ref<WizardState | null>(null)
const validation = ref<ValidationResult | null>(null)
const preview = ref<PreviewResult | null>(null)
const latexSnippet = ref<string | null>(null)

// Wizard form state
const selectedTemplate = ref<string>('')
const publicationFormat = ref<string>('ieee')
const exportFormat = ref<string>('latex')
const metadata = ref({
  title: '',
  authors: [''],
  abstract: '',
  keywords: [''],
})
const contentOptions = ref({
  include_tables: true,
  include_figures: true,
  include_methodology: false,
  include_citations: false,
})

// Table form state
const showTableModal = ref(false)
const tableForm = ref<{
  title: string
  caption: string
  label: string
  columns: { name: string; header: string }[]
  rows: Record<string, string>[]
}>({
  title: '',
  caption: '',
  label: '',
  columns: [{ name: 'col1', header: 'Column 1' }],
  rows: [{ col1: '' }],
})

// Plot form state
const showPlotModal = ref(false)
const plotForm = ref({
  plot_type: 'bar',
  title: '',
  xlabel: '',
  ylabel: '',
  x_data: '',
  y_data: '',
  labels: '',
  style_preset: 'ieee_single',
  format: 'png',
})
const plotResult = ref<PlotResult | null>(null)

// Preview state
const previewFormat = ref<string>('html')

// Computed
const currentStepIndex = computed(() => {
  const steps = ['format_selection', 'content_selection', 'style_configuration', 'preview']
  return steps.indexOf(wizardState.value?.current_step || 'format_selection')
})

const steps = [
  { id: 'format_selection', label: 'Format', icon: '1' },
  { id: 'content_selection', label: 'Content', icon: '2' },
  { id: 'style_configuration', label: 'Style', icon: '3' },
  { id: 'preview', label: 'Preview', icon: '4' },
]

// API Methods
async function fetchStatus() {
  try {
    const response = await fetch(`${API_BASE}/status`)
    if (!response.ok) throw new Error('Failed to fetch status')
    status.value = await response.json()
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

async function fetchTemplates() {
  try {
    const response = await fetch(`${API_BASE}/wizard/templates`)
    if (!response.ok) throw new Error('Failed to fetch templates')
    templates.value = await response.json()
  } catch (e) {
    console.error('Failed to fetch templates:', e)
  }
}

async function startWizard() {
  isLoading.value = true
  error.value = null
  try {
    const response = await fetch(`${API_BASE}/wizard/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template: selectedTemplate.value || null }),
    })
    if (!response.ok) throw new Error('Failed to start wizard')
    await response.json()
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to start wizard'
  } finally {
    isLoading.value = false
  }
}

async function fetchWizardState() {
  try {
    const response = await fetch(`${API_BASE}/wizard/state`)
    if (response.status === 404) {
      wizardState.value = null
      return
    }
    if (!response.ok) throw new Error('Failed to fetch wizard state')
    wizardState.value = await response.json()
  } catch (e) {
    console.error('Failed to fetch wizard state:', e)
  }
}

async function nextStep() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/next`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to move to next step')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to move to next step'
  } finally {
    isLoading.value = false
  }
}

async function previousStep() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/previous`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to move to previous step')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to move to previous step'
  } finally {
    isLoading.value = false
  }
}

async function goToStep(step: string) {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/go-to/${step}`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to go to step')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to go to step'
  } finally {
    isLoading.value = false
  }
}

async function setFormat() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/format`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        publication_format: publicationFormat.value,
        export_format: exportFormat.value,
      }),
    })
    if (!response.ok) throw new Error('Failed to set format')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to set format'
  } finally {
    isLoading.value = false
  }
}

async function setContent() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(contentOptions.value),
    })
    if (!response.ok) throw new Error('Failed to set content options')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to set content options'
  } finally {
    isLoading.value = false
  }
}

async function setMetadata() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/metadata`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: metadata.value.title,
        authors: metadata.value.authors.filter(a => a.trim()),
        abstract: metadata.value.abstract,
        keywords: metadata.value.keywords.filter(k => k.trim()),
      }),
    })
    if (!response.ok) throw new Error('Failed to set metadata')
    await fetchWizardState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to set metadata'
  } finally {
    isLoading.value = false
  }
}

async function validateWizard() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/validate`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to validate')
    validation.value = await response.json()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to validate'
  } finally {
    isLoading.value = false
  }
}

async function generatePreview() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format: previewFormat.value }),
    })
    if (!response.ok) throw new Error('Failed to generate preview')
    preview.value = await response.json()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to generate preview'
  } finally {
    isLoading.value = false
  }
}

async function getLatexSnippet() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/latex-snippet`, { method: 'POST' })
    if (!response.ok) throw new Error('Failed to get LaTeX snippet')
    const data = await response.json()
    latexSnippet.value = data.latex
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to get LaTeX snippet'
  } finally {
    isLoading.value = false
  }
}

async function addTable() {
  isLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/wizard/add-table`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tableForm.value),
    })
    if (!response.ok) throw new Error('Failed to add table')
    await fetchWizardState()
    showTableModal.value = false
    resetTableForm()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to add table'
  } finally {
    isLoading.value = false
  }
}

async function createPlot() {
  isLoading.value = true
  plotResult.value = null
  try {
    const payload: any = {
      plot_type: plotForm.value.plot_type,
      title: plotForm.value.title,
      xlabel: plotForm.value.xlabel,
      ylabel: plotForm.value.ylabel,
      style_preset: plotForm.value.style_preset,
      format: plotForm.value.format,
    }

    if (plotForm.value.x_data) {
      payload.x_data = JSON.parse(plotForm.value.x_data)
    }
    if (plotForm.value.y_data) {
      payload.y_data = JSON.parse(plotForm.value.y_data)
    }
    if (plotForm.value.labels) {
      payload.labels = JSON.parse(plotForm.value.labels)
    }

    const response = await fetch(`${API_BASE}/plots/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const errData = await response.json()
      throw new Error(errData.detail || 'Failed to create plot')
    }
    plotResult.value = await response.json()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create plot'
  } finally {
    isLoading.value = false
  }
}

// Helper methods
function resetTableForm() {
  tableForm.value = {
    title: '',
    caption: '',
    label: '',
    columns: [{ name: 'col1', header: 'Column 1' }],
    rows: [{ col1: '' }],
  }
}

function addAuthor() {
  metadata.value.authors.push('')
}

function removeAuthor(index: number) {
  if (metadata.value.authors.length > 1) {
    metadata.value.authors.splice(index, 1)
  }
}

function addKeyword() {
  metadata.value.keywords.push('')
}

function removeKeyword(index: number) {
  if (metadata.value.keywords.length > 1) {
    metadata.value.keywords.splice(index, 1)
  }
}

function addColumn() {
  const colNum = tableForm.value.columns.length + 1
  const colName = `col${colNum}`
  tableForm.value.columns.push({ name: colName, header: `Column ${colNum}` })
  tableForm.value.rows.forEach(row => {
    row[colName] = ''
  })
}

function addRow() {
  const newRow: Record<string, string> = {}
  tableForm.value.columns.forEach(col => {
    newRow[col.name] = ''
  })
  tableForm.value.rows.push(newRow)
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
  alert('Copied to clipboard!')
}

function getFormatIcon(format: string): string {
  const icons: Record<string, string> = {
    ieee: 'IEEE',
    acm: 'ACM',
    generic: 'GEN',
  }
  return icons[format] || format.toUpperCase()
}

// Lifecycle
onMounted(async () => {
  await Promise.all([fetchStatus(), fetchTemplates(), fetchWizardState()])
})
</script>

<template>
  <div class="export-view">
    <div class="header">
      <h2>Publication Export</h2>
      <div class="header-badges">
        <span v-if="status?.plot_generator" class="badge success">Plotting Available</span>
        <span v-else class="badge warning">Plotting Unavailable</span>
        <span class="badge info">S15 Features</span>
      </div>
    </div>

    <!-- Status Card -->
    <div class="status-card" v-if="status">
      <div class="status-grid">
        <div class="status-item">
          <span class="status-icon success">&#10003;</span>
          <span class="status-label">Publication Exporter</span>
        </div>
        <div class="status-item">
          <span :class="['status-icon', status.plot_generator ? 'success' : 'warning']">
            {{ status.plot_generator ? '&#10003;' : '!' }}
          </span>
          <span class="status-label">Plot Generator</span>
        </div>
        <div class="status-item">
          <span class="status-icon success">&#10003;</span>
          <span class="status-label">Jupyter Integration</span>
        </div>
        <div class="status-item">
          <span class="status-icon success">&#10003;</span>
          <span class="status-label">Export Wizard</span>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Template Selection (when no wizard active) -->
      <div v-if="!wizardState" class="template-section">
        <h3>Start Export Wizard</h3>
        <p class="section-description">
          Choose a template to quickly configure your export, or start from scratch.
        </p>

        <div class="templates-grid">
          <div
            v-for="template in templates"
            :key="template.template_id"
            :class="['template-card', { selected: selectedTemplate === template.template_id }]"
            @click="selectedTemplate = template.template_id"
          >
            <div class="template-icon">{{ getFormatIcon(template.publication_format) }}</div>
            <div class="template-info">
              <div class="template-name">{{ template.name }}</div>
              <div class="template-desc">{{ template.description }}</div>
              <div class="template-meta">
                <span>{{ template.figure_dpi }} DPI</span>
                <span>{{ template.column_count }} col</span>
              </div>
            </div>
          </div>
        </div>

        <div class="start-actions">
          <button class="btn btn-primary" @click="startWizard" :disabled="isLoading">
            {{ selectedTemplate ? 'Start with Template' : 'Start from Scratch' }}
          </button>
        </div>
      </div>

      <!-- Wizard Steps -->
      <div v-else class="wizard-section">
        <!-- Step Indicator -->
        <div class="step-indicator">
          <div
            v-for="(step, index) in steps"
            :key="step.id"
            :class="['step', { active: currentStepIndex === index, completed: currentStepIndex > index }]"
            @click="goToStep(step.id)"
          >
            <span class="step-number">{{ step.icon }}</span>
            <span class="step-label">{{ step.label }}</span>
          </div>
        </div>

        <!-- Step Content -->
        <div class="step-content">
          <!-- Step 1: Format Selection -->
          <div v-if="wizardState.current_step === 'format_selection'" class="step-panel">
            <h3>Select Publication Format</h3>

            <div class="form-group">
              <label>Publication Format</label>
              <div class="format-options">
                <label class="format-option">
                  <input type="radio" v-model="publicationFormat" value="ieee" />
                  <span class="format-box">
                    <span class="format-icon">IEEE</span>
                    <span>IEEE Format</span>
                  </span>
                </label>
                <label class="format-option">
                  <input type="radio" v-model="publicationFormat" value="acm" />
                  <span class="format-box">
                    <span class="format-icon">ACM</span>
                    <span>ACM Format</span>
                  </span>
                </label>
                <label class="format-option">
                  <input type="radio" v-model="publicationFormat" value="generic" />
                  <span class="format-box">
                    <span class="format-icon">GEN</span>
                    <span>Generic</span>
                  </span>
                </label>
              </div>
            </div>

            <div class="form-group">
              <label>Export Format</label>
              <select v-model="exportFormat" class="form-select">
                <option value="latex">LaTeX</option>
                <option value="markdown">Markdown</option>
                <option value="html">HTML</option>
              </select>
            </div>

            <button class="btn btn-primary" @click="setFormat(); nextStep()">
              Continue
            </button>
          </div>

          <!-- Step 2: Content Selection -->
          <div v-if="wizardState.current_step === 'content_selection'" class="step-panel">
            <h3>Content Options</h3>

            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="contentOptions.include_tables" />
                <span>Include Tables</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="contentOptions.include_figures" />
                <span>Include Figures</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="contentOptions.include_methodology" />
                <span>Include Methodology</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="contentOptions.include_citations" />
                <span>Include Citations</span>
              </label>
            </div>

            <div class="content-summary" v-if="wizardState">
              <h4>Current Content</h4>
              <div class="summary-row">
                <span>Tables:</span>
                <span>{{ wizardState.table_count }}</span>
                <button class="btn btn-sm" @click="showTableModal = true">Add Table</button>
              </div>
              <div class="summary-row">
                <span>Figures:</span>
                <span>{{ wizardState.figure_count }}</span>
              </div>
              <div class="summary-row">
                <span>Citations:</span>
                <span>{{ wizardState.citation_count }}</span>
              </div>
            </div>

            <div class="step-actions">
              <button class="btn" @click="previousStep">Back</button>
              <button class="btn btn-primary" @click="setContent(); nextStep()">
                Continue
              </button>
            </div>
          </div>

          <!-- Step 3: Style Configuration (Metadata) -->
          <div v-if="wizardState.current_step === 'style_configuration'" class="step-panel">
            <h3>Publication Metadata</h3>

            <div class="form-group">
              <label>Title</label>
              <input type="text" v-model="metadata.title" placeholder="Your publication title" />
            </div>

            <div class="form-group">
              <label>Authors</label>
              <div class="array-input">
                <div v-for="(_author, index) in metadata.authors" :key="index" class="array-item">
                  <input type="text" v-model="metadata.authors[index]" placeholder="Author name" />
                  <button class="btn-icon" @click="removeAuthor(index)" v-if="metadata.authors.length > 1">
                    &times;
                  </button>
                </div>
                <button class="btn btn-sm" @click="addAuthor">+ Add Author</button>
              </div>
            </div>

            <div class="form-group">
              <label>Abstract</label>
              <textarea v-model="metadata.abstract" rows="4" placeholder="Publication abstract"></textarea>
            </div>

            <div class="form-group">
              <label>Keywords</label>
              <div class="array-input">
                <div v-for="(_keyword, index) in metadata.keywords" :key="index" class="array-item">
                  <input type="text" v-model="metadata.keywords[index]" placeholder="Keyword" />
                  <button class="btn-icon" @click="removeKeyword(index)" v-if="metadata.keywords.length > 1">
                    &times;
                  </button>
                </div>
                <button class="btn btn-sm" @click="addKeyword">+ Add Keyword</button>
              </div>
            </div>

            <div class="step-actions">
              <button class="btn" @click="previousStep">Back</button>
              <button class="btn btn-primary" @click="setMetadata(); nextStep()">
                Continue to Preview
              </button>
            </div>
          </div>

          <!-- Step 4: Preview -->
          <div v-if="wizardState.current_step === 'preview'" class="step-panel">
            <h3>Preview & Export</h3>

            <div class="preview-controls">
              <div class="form-group inline">
                <label>Preview Format:</label>
                <select v-model="previewFormat" class="form-select-sm">
                  <option value="html">HTML</option>
                  <option value="text">Plain Text</option>
                  <option value="json">JSON</option>
                </select>
              </div>
              <button class="btn" @click="generatePreview" :disabled="isLoading">
                Generate Preview
              </button>
              <button class="btn" @click="getLatexSnippet" :disabled="isLoading">
                Get LaTeX
              </button>
              <button class="btn" @click="validateWizard" :disabled="isLoading">
                Validate
              </button>
            </div>

            <!-- Validation Results -->
            <div v-if="validation" :class="['validation-box', validation.valid ? 'success' : 'error']">
              <div class="validation-header">
                {{ validation.valid ? '&#10003; Configuration Valid' : '&#10007; Validation Errors' }}
              </div>
              <ul v-if="validation.errors.length" class="validation-list">
                <li v-for="err in validation.errors" :key="err" class="error-item">{{ err }}</li>
              </ul>
              <ul v-if="validation.warnings.length" class="validation-list">
                <li v-for="warn in validation.warnings" :key="warn" class="warning-item">{{ warn }}</li>
              </ul>
            </div>

            <!-- Preview Content -->
            <div v-if="preview" class="preview-box">
              <div class="preview-header">
                <span>Preview ({{ preview.format }})</span>
                <span class="preview-stats">
                  {{ preview.word_count }} words |
                  {{ preview.table_count }} tables |
                  {{ preview.figure_count }} figures
                </span>
                <button class="btn btn-sm" @click="copyToClipboard(preview.content)">Copy</button>
              </div>
              <div class="preview-content" v-html="preview.content" v-if="preview.format === 'html'"></div>
              <pre class="preview-content" v-else>{{ preview.content }}</pre>
            </div>

            <!-- LaTeX Snippet -->
            <div v-if="latexSnippet" class="latex-box">
              <div class="latex-header">
                <span>LaTeX Snippet</span>
                <button class="btn btn-sm" @click="copyToClipboard(latexSnippet)">Copy</button>
              </div>
              <pre class="latex-content">{{ latexSnippet }}</pre>
            </div>

            <div class="step-actions">
              <button class="btn" @click="previousStep">Back</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Plot Generator Section -->
      <div class="plot-section">
        <h3>Plot Generator</h3>
        <p class="section-description">
          Create publication-quality plots for your research papers.
        </p>

        <button class="btn" @click="showPlotModal = true" :disabled="!status?.plot_generator">
          Create New Plot
        </button>

        <div v-if="!status?.plot_generator" class="warning-box">
          Plot generator unavailable. Missing dependencies: {{ status?.missing_plot_dependencies?.join(', ') }}
        </div>
      </div>
    </div>

    <!-- Table Modal -->
    <div v-if="showTableModal" class="modal-overlay" @click.self="showTableModal = false">
      <div class="modal modal-lg">
        <h3>Add Table</h3>

        <div class="form-group">
          <label>Title</label>
          <input type="text" v-model="tableForm.title" placeholder="Table title" />
        </div>

        <div class="form-group">
          <label>Caption</label>
          <input type="text" v-model="tableForm.caption" placeholder="Table caption" />
        </div>

        <div class="form-group">
          <label>Label (for LaTeX ref)</label>
          <input type="text" v-model="tableForm.label" placeholder="tab:results" />
        </div>

        <div class="form-group">
          <label>Columns</label>
          <div class="columns-editor">
            <div v-for="(col, index) in tableForm.columns" :key="index" class="column-row">
              <input type="text" v-model="col.header" placeholder="Column header" />
            </div>
            <button class="btn btn-sm" @click="addColumn">+ Add Column</button>
          </div>
        </div>

        <div class="form-group">
          <label>Data Rows</label>
          <div class="rows-editor">
            <div v-for="(row, rowIndex) in tableForm.rows" :key="rowIndex" class="data-row">
              <input
                v-for="col in tableForm.columns"
                :key="col.name"
                type="text"
                v-model="row[col.name]"
                :placeholder="col.header"
              />
            </div>
            <button class="btn btn-sm" @click="addRow">+ Add Row</button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn" @click="showTableModal = false">Cancel</button>
          <button class="btn btn-primary" @click="addTable" :disabled="isLoading">Add Table</button>
        </div>
      </div>
    </div>

    <!-- Plot Modal -->
    <div v-if="showPlotModal" class="modal-overlay" @click.self="showPlotModal = false">
      <div class="modal modal-lg">
        <h3>Create Plot</h3>

        <div class="form-row">
          <div class="form-group">
            <label>Plot Type</label>
            <select v-model="plotForm.plot_type" class="form-select">
              <option value="line">Line</option>
              <option value="bar">Bar</option>
              <option value="scatter">Scatter</option>
              <option value="heatmap">Heatmap</option>
              <option value="box">Box</option>
              <option value="histogram">Histogram</option>
            </select>
          </div>
          <div class="form-group">
            <label>Style Preset</label>
            <select v-model="plotForm.style_preset" class="form-select">
              <option value="ieee_single">IEEE Single Column</option>
              <option value="ieee_double">IEEE Double Column</option>
              <option value="acm">ACM</option>
              <option value="presentation">Presentation</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>Title</label>
          <input type="text" v-model="plotForm.title" placeholder="Plot title" />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>X Label</label>
            <input type="text" v-model="plotForm.xlabel" placeholder="X axis label" />
          </div>
          <div class="form-group">
            <label>Y Label</label>
            <input type="text" v-model="plotForm.ylabel" placeholder="Y axis label" />
          </div>
        </div>

        <div class="form-group">
          <label>X Data (JSON array)</label>
          <input type="text" v-model="plotForm.x_data" placeholder='["A", "B", "C"] or [1, 2, 3]' />
        </div>

        <div class="form-group">
          <label>Y Data (JSON array)</label>
          <input type="text" v-model="plotForm.y_data" placeholder="[10, 20, 30]" />
        </div>

        <div class="form-group">
          <label>Labels (optional, JSON array)</label>
          <input type="text" v-model="plotForm.labels" placeholder='["Series 1", "Series 2"]' />
        </div>

        <div class="form-group">
          <label>Output Format</label>
          <select v-model="plotForm.format" class="form-select">
            <option value="png">PNG</option>
            <option value="pdf">PDF</option>
            <option value="svg">SVG</option>
            <option value="eps">EPS</option>
          </select>
        </div>

        <!-- Plot Result -->
        <div v-if="plotResult" class="plot-result">
          <div class="result-header">
            <span class="success">&#10003; Plot Created</span>
            <span class="result-info">{{ plotResult.file_size_bytes }} bytes</span>
          </div>
          <img
            v-if="plotResult.base64_data && plotForm.format === 'png'"
            :src="'data:image/png;base64,' + plotResult.base64_data"
            alt="Generated plot"
            class="result-image"
          />
          <div class="result-path">Saved to: {{ plotResult.output_path }}</div>
        </div>

        <div class="modal-actions">
          <button class="btn" @click="showPlotModal = false">Close</button>
          <button class="btn btn-primary" @click="createPlot" :disabled="isLoading">
            {{ isLoading ? 'Creating...' : 'Create Plot' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Error Toast -->
    <div v-if="error" class="error-toast" @click="error = null">
      {{ error }}
    </div>
  </div>
</template>

<style scoped>
.export-view {
  padding: var(--spacing-lg);
  height: 100%;
  overflow-y: auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.header h2 {
  margin: 0;
}

.header-badges {
  display: flex;
  gap: var(--spacing-sm);
}

.badge {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.success {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.badge.warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.badge.info {
  background: rgba(0, 217, 255, 0.2);
  color: var(--color-primary);
}

/* Status Card */
.status-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.status-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.status-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 700;
}

.status-icon.success {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.status-icon.warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.status-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* Main Content */
.main-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* Template Section */
.template-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.template-section h3 {
  margin: 0 0 var(--spacing-sm) 0;
}

.section-description {
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.template-card {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  border-color: var(--color-primary);
}

.template-card.selected {
  border-color: var(--color-primary);
  background: rgba(0, 217, 255, 0.1);
}

.template-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--color-primary);
}

.template-info {
  flex: 1;
}

.template-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.template-desc {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.template-meta {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 0.7rem;
  color: var(--text-tertiary);
}

.start-actions {
  display: flex;
  justify-content: center;
}

/* Wizard Section */
.wizard-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

/* Step Indicator */
.step-indicator {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-xl);
  position: relative;
}

.step-indicator::before {
  content: '';
  position: absolute;
  top: 16px;
  left: 40px;
  right: 40px;
  height: 2px;
  background: var(--bg-input);
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  cursor: pointer;
  z-index: 1;
}

.step-number {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-input);
  color: var(--text-secondary);
  font-weight: 600;
  transition: all 0.2s;
}

.step.active .step-number {
  background: var(--color-primary);
  color: white;
}

.step.completed .step-number {
  background: #4caf50;
  color: white;
}

.step-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.step.active .step-label {
  color: var(--color-primary);
  font-weight: 600;
}

/* Step Content */
.step-content {
  min-height: 400px;
}

.step-panel h3 {
  margin: 0 0 var(--spacing-lg) 0;
}

/* Form Elements */
.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.form-group input,
.form-group textarea,
.form-select {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--bg-input);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}

.form-group input:focus,
.form-group textarea:focus,
.form-select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-select-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.875rem;
}

.form-group.inline {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.form-group.inline label {
  margin-bottom: 0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

/* Format Options */
.format-options {
  display: flex;
  gap: var(--spacing-md);
}

.format-option {
  cursor: pointer;
}

.format-option input {
  display: none;
}

.format-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  min-width: 100px;
  transition: all 0.2s;
}

.format-option input:checked + .format-box {
  border-color: var(--color-primary);
  background: rgba(0, 217, 255, 0.1);
}

.format-icon {
  font-weight: 700;
  font-size: 1.25rem;
  color: var(--color-primary);
}

/* Checkbox Group */
.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.checkbox-label input {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
}

/* Content Summary */
.content-summary {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.content-summary h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.summary-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
}

.summary-row span:first-child {
  color: var(--text-secondary);
  min-width: 80px;
}

.summary-row span:nth-child(2) {
  color: var(--text-primary);
  font-weight: 600;
  flex: 1;
}

/* Array Input */
.array-input {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.array-item {
  display: flex;
  gap: var(--spacing-sm);
}

.array-item input {
  flex: 1;
}

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(244, 67, 54, 0.2);
  border: none;
  border-radius: var(--radius-sm);
  color: #f44336;
  cursor: pointer;
  font-size: 1.25rem;
}

.btn-icon:hover {
  background: rgba(244, 67, 54, 0.3);
}

/* Step Actions */
.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--bg-input);
}

/* Preview Controls */
.preview-controls {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

/* Validation Box */
.validation-box {
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
}

.validation-box.success {
  background: rgba(76, 175, 80, 0.1);
  border: 1px solid rgba(76, 175, 80, 0.3);
}

.validation-box.error {
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
}

.validation-header {
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
}

.validation-box.success .validation-header {
  color: #4caf50;
}

.validation-box.error .validation-header {
  color: #f44336;
}

.validation-list {
  margin: 0;
  padding-left: var(--spacing-lg);
}

.error-item {
  color: #f44336;
}

.warning-item {
  color: #ff9800;
}

/* Preview Box */
.preview-box {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-card);
  border-bottom: 1px solid var(--bg-input);
}

.preview-stats {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.preview-content {
  padding: var(--spacing-md);
  max-height: 400px;
  overflow-y: auto;
  font-size: 0.875rem;
}

pre.preview-content {
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

/* LaTeX Box */
.latex-box {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.latex-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-card);
  border-bottom: 1px solid var(--bg-input);
}

.latex-content {
  padding: var(--spacing-md);
  font-family: monospace;
  font-size: 0.875rem;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* Plot Section */
.plot-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.plot-section h3 {
  margin: 0 0 var(--spacing-sm) 0;
}

.warning-box {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: var(--radius-md);
  color: #ffc107;
  font-size: 0.875rem;
}

/* Plot Result */
.plot-result {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: rgba(76, 175, 80, 0.1);
  border: 1px solid rgba(76, 175, 80, 0.3);
  border-radius: var(--radius-md);
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.result-header .success {
  color: #4caf50;
  font-weight: 600;
}

.result-info {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.result-image {
  max-width: 100%;
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
}

.result-path {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-family: monospace;
}

/* Modal */
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
}

.modal {
  background: var(--bg-card);
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  width: 500px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-lg {
  width: 700px;
}

.modal h3 {
  margin: 0 0 var(--spacing-lg) 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--bg-input);
}

/* Table Editor */
.columns-editor,
.rows-editor {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.column-row {
  display: flex;
  gap: var(--spacing-sm);
}

.data-row {
  display: flex;
  gap: var(--spacing-sm);
}

.data-row input {
  flex: 1;
}

/* Buttons */
.btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.btn:hover {
  background: var(--bg-card);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background: #00b8d9;
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: 0.75rem;
}

/* Error Toast */
.error-toast {
  position: fixed;
  bottom: var(--spacing-lg);
  right: var(--spacing-lg);
  padding: var(--spacing-md) var(--spacing-lg);
  background: rgba(244, 67, 54, 0.9);
  color: white;
  border-radius: var(--radius-md);
  cursor: pointer;
  z-index: 1100;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
