<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ragApi, type CollectionStatsItem } from '@/services/ragApi'

// Types
interface Document {
  id: string
  name: string
  type: 'pdf' | 'json' | 'csv' | 'txt' | 'md'
  collection: string
  size: number
  chunks: number
  uploadedAt: Date
  status: 'indexed' | 'processing' | 'failed'
  metadata?: Record<string, string>
}

interface Collection {
  id: string
  name: string
  description: string
  documentCount: number
  chunkCount: number
  icon: string
  color: string
}

interface SearchResult {
  id: string
  documentName: string
  collection: string
  content: string
  similarity: number
  metadata?: Record<string, string>
}

// RAG API connection state
const isApiAvailable = ref(false)
const isLoadingStats = ref(false)
const apiError = ref<string | null>(null)
const totalDocsFromApi = ref(0)

// Indexing state
const isIndexing = ref(false)
const indexingResult = ref<{ success: boolean; message: string } | null>(null)

// Add document modal state
const showAddDocModal = ref(false)
const newDocTitle = ref('')
const newDocContent = ref('')
const newDocCategory = ref('')
const newDocSource = ref('')
const newDocTags = ref('')
const isAddingDoc = ref(false)

// Collection icon/color mapping
const collectionMeta: Record<string, { icon: string; color: string; description: string }> = {
  security_research: { icon: '📄', color: '#6366f1', description: 'Security research papers and publications' },
  attack_patterns: { icon: '⚔️', color: '#dc2626', description: 'MITRE ATT&CK and attack patterns' },
  device_manuals: { icon: '📱', color: '#f97316', description: 'IoT device specifications and manuals' },
  network_protocols: { icon: '🌐', color: '#22c55e', description: 'Network protocol documentation' },
  threat_intelligence: { icon: '🛡️', color: '#8b5cf6', description: 'Threat intelligence feeds and CVEs' },
  default: { icon: '📁', color: '#6b7280', description: 'General documents' },
}

// State
const collections = ref<Collection[]>([])

const documents = ref<Document[]>([])

const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const isSearching = ref(false)
const selectedCollection = ref<string | null>(null)
const selectedDocument = ref<Document | null>(null)
const isDragging = ref(false)
const uploadProgress = ref(0)
const isUploading = ref(false)

// Initialize - fetch stats from RAG API
async function initializeFromApi() {
  isLoadingStats.value = true
  apiError.value = null

  try {
    // Check API availability
    isApiAvailable.value = await ragApi.checkAvailability()

    if (!isApiAvailable.value) {
      apiError.value = 'RAG API is not available. Showing mock data.'
      loadMockData()
      return
    }

    // Fetch comprehensive stats
    const stats = await ragApi.getComprehensiveStats()

    // Store total documents from main collection
    totalDocsFromApi.value = stats.total_documents

    // Convert API collections to our format
    collections.value = stats.collections.map((col: CollectionStatsItem) => {
      const meta = collectionMeta[col.collection_name] || collectionMeta.default
      return {
        id: col.collection_name,
        name: formatCollectionName(col.collection_name),
        description: meta.description,
        documentCount: col.document_count,
        chunkCount: col.chunk_count,
        icon: meta.icon,
        color: meta.color,
      }
    })

    // If no collections, add defaults
    if (collections.value.length === 0) {
      const defaultCollections = await ragApi.listCollections()
      collections.value = defaultCollections.map(name => {
        const meta = collectionMeta[name] || collectionMeta.default
        return {
          id: name,
          name: formatCollectionName(name),
          description: meta.description,
          documentCount: 0,
          chunkCount: 0,
          icon: meta.icon,
          color: meta.color,
        }
      })
    }
  } catch (err) {
    console.error('Failed to initialize from API:', err)
    apiError.value = 'Failed to connect to RAG API. Showing mock data.'
    loadMockData()
  } finally {
    isLoadingStats.value = false
  }
}

function formatCollectionName(name: string): string {
  return name
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function loadMockData() {
  collections.value = [
    {
      id: 'security_research',
      name: 'Security Research',
      description: 'Security research papers and publications',
      documentCount: 45,
      chunkCount: 1250,
      icon: '📄',
      color: '#6366f1'
    },
    {
      id: 'attack_patterns',
      name: 'Attack Patterns',
      description: 'MITRE ATT&CK and attack patterns',
      documentCount: 234,
      chunkCount: 5600,
      icon: '⚔️',
      color: '#dc2626'
    },
    {
      id: 'device_manuals',
      name: 'Device Manuals',
      description: 'IoT device specifications and manuals',
      documentCount: 89,
      chunkCount: 2100,
      icon: '📱',
      color: '#f97316'
    },
    {
      id: 'network_protocols',
      name: 'Network Protocols',
      description: 'Network protocol documentation',
      documentCount: 12,
      chunkCount: 380,
      icon: '🌐',
      color: '#22c55e'
    },
    {
      id: 'threat_intelligence',
      name: 'Threat Intelligence',
      description: 'Threat intelligence feeds and CVEs',
      documentCount: 8,
      chunkCount: 180,
      icon: '🛡️',
      color: '#8b5cf6'
    }
  ]

  documents.value = [
    {
      id: 'doc-1',
      name: 'IoT Botnet Detection Survey 2024.pdf',
      type: 'pdf',
      collection: 'security_research',
      size: 2450000,
      chunks: 85,
      uploadedAt: new Date('2024-12-01'),
      status: 'indexed',
      metadata: { author: 'Smith et al.', year: '2024' }
    },
    {
      id: 'doc-2',
      name: 'MITRE_ATT&CK_IoT.json',
      type: 'json',
      collection: 'attack_patterns',
      size: 890000,
      chunks: 450,
      uploadedAt: new Date('2024-11-25'),
      status: 'indexed'
    },
  ]
}

onMounted(() => {
  initializeFromApi()
})

// Computed
const totalDocuments = computed(() => {
  // If API has documents but collections show 0, use API count
  const collectionSum = collections.value.reduce((sum, c) => sum + c.documentCount, 0)
  return totalDocsFromApi.value > collectionSum ? totalDocsFromApi.value : collectionSum
})
const totalChunks = computed(() => collections.value.reduce((sum, c) => sum + c.chunkCount, 0))
const filteredDocuments = computed(() => {
  if (!selectedCollection.value) return documents.value
  return documents.value.filter(d => d.collection === selectedCollection.value)
})

const storageUsed = computed(() => {
  const total = documents.value.reduce((sum, d) => sum + d.size, 0)
  return formatFileSize(total)
})

// Methods
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function getFileIcon(type: Document['type']): string {
  const icons: Record<Document['type'], string> = {
    pdf: '📄',
    json: '📋',
    csv: '📊',
    txt: '📝',
    md: '📑'
  }
  return icons[type]
}

function getStatusColor(status: Document['status']): string {
  const colors: Record<Document['status'], string> = {
    indexed: '#22c55e',
    processing: '#eab308',
    failed: '#dc2626'
  }
  return colors[status]
}

function selectCollection(collectionId: string | null) {
  selectedCollection.value = selectedCollection.value === collectionId ? null : collectionId
  selectedDocument.value = null
}

function selectDocument(doc: Document) {
  selectedDocument.value = selectedDocument.value?.id === doc.id ? null : doc
}

async function performSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  isSearching.value = true

  try {
    // Try to use RAG API if available
    if (isApiAvailable.value) {
      const response = await ragApi.search({
        query: searchQuery.value,
        n_results: 10,
        category: selectedCollection.value || undefined,
      })

      // Convert API results to our format
      searchResults.value = response.results.map((r, i) => ({
        id: `result-${i}`,
        documentName: r.title || r.source || 'Unknown Document',
        collection: r.category || 'default',
        content: r.content,
        similarity: r.similarity_score,
        metadata: r.source ? { source: r.source } : undefined,
      }))
    } else {
      // Fallback to mock results
      await new Promise(resolve => setTimeout(resolve, 800))

      const mockResults: SearchResult[] = [
        {
          id: 'result-1',
          documentName: 'IoT Botnet Detection Survey 2024.pdf',
          collection: 'security_research',
          content: `...${searchQuery.value}... is a critical aspect of IoT security. Recent studies have shown that machine learning approaches can effectively detect botnet activity in smart home networks with 95% accuracy...`,
          similarity: 0.94,
          metadata: { page: '15', section: 'Machine Learning Methods' }
        },
        {
          id: 'result-2',
          documentName: 'MITRE_ATT&CK_IoT.json',
          collection: 'attack_patterns',
          content: `Technique: ${searchQuery.value} - Initial Access technique targeting IoT devices through default credentials and unpatched vulnerabilities. Commonly used by Mirai variants...`,
          similarity: 0.87,
          metadata: { technique_id: 'T1078', tactic: 'Initial Access' }
        },
        {
          id: 'result-3',
          documentName: 'Smart Home Intrusion Dataset.csv',
          collection: 'network_protocols',
          content: `Dataset contains network traffic patterns related to ${searchQuery.value}. Features include packet size distribution, connection duration, protocol usage statistics...`,
          similarity: 0.82
        },
        {
          id: 'result-4',
          documentName: 'Zigbee Protocol Specification.pdf',
          collection: 'device_manuals',
          content: `...security considerations for ${searchQuery.value}... The protocol implements AES-128 encryption for frame protection. Key management follows...`,
          similarity: 0.76,
          metadata: { section: 'Security Layer', page: '89' }
        }
      ]

      searchResults.value = mockResults
    }
  } catch (err) {
    console.error('Search failed:', err)
    // Show error but don't break the UI
    searchResults.value = [{
      id: 'error',
      documentName: 'Search Error',
      collection: 'default',
      content: 'Failed to perform search. Please check your connection and try again.',
      similarity: 0,
    }]
  } finally {
    isSearching.value = false
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false

  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    uploadFiles(Array.from(files))
  }
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    uploadFiles(Array.from(input.files))
  }
}

async function uploadFiles(files: File[]) {
  isUploading.value = true
  uploadProgress.value = 0

  for (let i = 0; i < files.length; i++) {
    const file = files[i]

    // Simulate upload progress
    for (let p = 0; p <= 100; p += 10) {
      uploadProgress.value = p
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    // Add to documents
    const fileType = file.name.split('.').pop()?.toLowerCase() as Document['type']
    const newDoc: Document = {
      id: `doc-${Date.now()}`,
      name: file.name,
      type: fileType || 'txt',
      collection: selectedCollection.value || 'user_uploads',
      size: file.size,
      chunks: Math.ceil(file.size / 1024),
      uploadedAt: new Date(),
      status: 'processing'
    }

    documents.value.unshift(newDoc)

    // Simulate indexing completion
    setTimeout(() => {
      const doc = documents.value.find(d => d.id === newDoc.id)
      if (doc) {
        doc.status = 'indexed'
        // Update collection stats
        const collection = collections.value.find(c => c.id === doc.collection)
        if (collection) {
          collection.documentCount++
          collection.chunkCount += doc.chunks
        }
      }
    }, 3000)
  }

  isUploading.value = false
  uploadProgress.value = 0
}

function deleteDocument(docId: string) {
  const docIndex = documents.value.findIndex(d => d.id === docId)
  if (docIndex !== -1) {
    const doc = documents.value[docIndex]
    // Update collection stats
    const collection = collections.value.find(c => c.id === doc.collection)
    if (collection) {
      collection.documentCount--
      collection.chunkCount -= doc.chunks
    }
    documents.value.splice(docIndex, 1)
    if (selectedDocument.value?.id === docId) {
      selectedDocument.value = null
    }
  }
}

// Re-index knowledge base from directory
async function reindexKnowledgeBase() {
  if (!isApiAvailable.value || isIndexing.value) return

  isIndexing.value = true
  indexingResult.value = null

  try {
    const result = await ragApi.ingestDirectory({ recursive: true })
    indexingResult.value = {
      success: true,
      message: `Indexed ${result.documents_ingested} documents from ${result.source_directory}`
    }
    // Refresh stats after indexing
    await initializeFromApi()
  } catch (err) {
    console.error('Indexing failed:', err)
    indexingResult.value = {
      success: false,
      message: err instanceof Error ? err.message : 'Indexing failed'
    }
  } finally {
    isIndexing.value = false
    // Clear message after 5 seconds
    setTimeout(() => {
      indexingResult.value = null
    }, 5000)
  }
}

// Add document via API
async function addDocumentViaApi() {
  if (!isApiAvailable.value || isAddingDoc.value) return
  if (!newDocTitle.value.trim() || !newDocContent.value.trim()) return

  isAddingDoc.value = true

  try {
    await ragApi.addDocumentsBatch([{
      title: newDocTitle.value.trim(),
      content: newDocContent.value.trim(),
      category: newDocCategory.value.trim() || 'user_uploads',
      source: newDocSource.value.trim() || 'user_input',
      tags: newDocTags.value.split(',').map(t => t.trim()).filter(t => t),
    }])

    // Add to local documents list
    const newDoc: Document = {
      id: `doc-${Date.now()}`,
      name: newDocTitle.value.trim(),
      type: 'txt',
      collection: newDocCategory.value.trim() || 'user_uploads',
      size: new Blob([newDocContent.value]).size,
      chunks: Math.ceil(newDocContent.value.length / 500),
      uploadedAt: new Date(),
      status: 'indexed',
      metadata: { source: newDocSource.value || 'user_input' }
    }
    documents.value.unshift(newDoc)

    // Update collection stats
    const collection = collections.value.find(c => c.id === newDoc.collection)
    if (collection) {
      collection.documentCount++
      collection.chunkCount += newDoc.chunks
    }

    // Reset form and close modal
    resetAddDocForm()
    showAddDocModal.value = false

    // Refresh stats
    await initializeFromApi()
  } catch (err) {
    console.error('Failed to add document:', err)
    apiError.value = err instanceof Error ? err.message : 'Failed to add document'
  } finally {
    isAddingDoc.value = false
  }
}

function resetAddDocForm() {
  newDocTitle.value = ''
  newDocContent.value = ''
  newDocCategory.value = ''
  newDocSource.value = ''
  newDocTags.value = ''
}

function openAddDocModal() {
  resetAddDocForm()
  showAddDocModal.value = true
}
</script>

<template>
  <div class="knowledge-base">
    <!-- Header -->
    <div class="kb-header">
      <div class="header-title">
        <h1>Knowledge Base</h1>
        <p>Manage and search your RAG knowledge repository</p>
      </div>
      <div class="header-stats">
        <div class="header-stat">
          <span class="stat-value">{{ totalDocuments }}</span>
          <span class="stat-label">Documents</span>
        </div>
        <div class="header-stat">
          <span class="stat-value">{{ totalChunks.toLocaleString() }}</span>
          <span class="stat-label">Chunks</span>
        </div>
        <div class="header-stat">
          <span class="stat-value">{{ storageUsed }}</span>
          <span class="stat-label">Storage</span>
        </div>
      </div>
      <div class="header-actions">
        <button
          v-if="isApiAvailable"
          class="btn btn-ghost"
          @click="openAddDocModal"
          title="Add a new document to the knowledge base"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"></path>
          </svg>
          Add Document
        </button>
        <button
          v-if="isApiAvailable"
          class="btn btn-primary"
          :disabled="isIndexing"
          @click="reindexKnowledgeBase"
          title="Re-index documents from knowledge_base directory"
        >
          <svg v-if="!isIndexing" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9"></path>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
          </svg>
          {{ isIndexing ? 'Indexing...' : 'Re-index' }}
        </button>
      </div>
    </div>

    <!-- Indexing Result Message -->
    <div v-if="indexingResult" class="indexing-result" :class="{ success: indexingResult.success, error: !indexingResult.success }">
      <span>{{ indexingResult.success ? '✓' : '✗' }}</span>
      {{ indexingResult.message }}
    </div>

    <!-- Search Bar -->
    <div class="search-section">
      <div class="search-bar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search knowledge base with natural language..."
          @keyup.enter="performSearch"
        />
        <button class="btn btn-primary" @click="performSearch" :disabled="isSearching">
          {{ isSearching ? 'Searching...' : 'Search' }}
        </button>
      </div>
    </div>

    <!-- Search Results -->
    <div v-if="searchResults.length > 0" class="search-results">
      <div class="results-header">
        <h2>Search Results</h2>
        <button class="btn btn-ghost btn-sm" @click="searchResults = []">Clear Results</button>
      </div>
      <div class="results-list">
        <div v-for="result in searchResults" :key="result.id" class="result-card">
          <div class="result-header">
            <span class="result-doc">{{ result.documentName }}</span>
            <span class="result-similarity" :style="{ color: result.similarity > 0.9 ? '#22c55e' : result.similarity > 0.8 ? '#eab308' : '#f97316' }">
              {{ (result.similarity * 100).toFixed(0) }}% match
            </span>
          </div>
          <div class="result-collection">
            {{ collections.find(c => c.id === result.collection)?.name }}
          </div>
          <p class="result-content">{{ result.content }}</p>
          <div v-if="result.metadata" class="result-metadata">
            <span v-for="(value, key) in result.metadata" :key="key" class="metadata-tag">
              {{ key }}: {{ value }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="kb-content">
      <!-- Collections Sidebar -->
      <aside class="collections-sidebar">
        <h2>Collections</h2>
        <div class="collections-list">
          <div
            v-for="collection in collections"
            :key="collection.id"
            class="collection-card"
            :class="{ selected: selectedCollection === collection.id }"
            :style="{ '--collection-color': collection.color }"
            @click="selectCollection(collection.id)"
          >
            <span class="collection-icon">{{ collection.icon }}</span>
            <div class="collection-info">
              <h3>{{ collection.name }}</h3>
              <p>{{ collection.description }}</p>
              <div class="collection-stats">
                <span>{{ collection.documentCount }} docs</span>
                <span>{{ collection.chunkCount.toLocaleString() }} chunks</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Documents Area -->
      <main class="documents-area">
        <!-- Upload Zone -->
        <div
          class="upload-zone"
          :class="{ dragging: isDragging, uploading: isUploading }"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
        >
          <div v-if="isUploading" class="upload-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <span>Uploading and indexing... {{ uploadProgress }}%</span>
          </div>
          <template v-else>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <p>Drag and drop files here, or <label class="upload-link">browse<input type="file" multiple @change="handleFileSelect" hidden /></label></p>
            <span class="upload-hint">Supported: PDF, JSON, CSV, TXT, MD</span>
          </template>
        </div>

        <!-- Documents List -->
        <div class="documents-section">
          <div class="section-header">
            <h2>Documents {{ selectedCollection ? `in ${collections.find(c => c.id === selectedCollection)?.name}` : '' }}</h2>
            <span class="doc-count">{{ filteredDocuments.length }} documents</span>
          </div>
          <div class="documents-list">
            <div
              v-for="doc in filteredDocuments"
              :key="doc.id"
              class="document-card"
              :class="{ selected: selectedDocument?.id === doc.id }"
              @click="selectDocument(doc)"
            >
              <span class="doc-icon">{{ getFileIcon(doc.type) }}</span>
              <div class="doc-info">
                <h4>{{ doc.name }}</h4>
                <div class="doc-meta">
                  <span>{{ formatFileSize(doc.size) }}</span>
                  <span>{{ doc.chunks }} chunks</span>
                  <span>{{ formatDate(doc.uploadedAt) }}</span>
                </div>
              </div>
              <div class="doc-status" :style="{ color: getStatusColor(doc.status) }">
                <span class="status-dot" :style="{ backgroundColor: getStatusColor(doc.status) }"></span>
                {{ doc.status }}
              </div>
              <button class="doc-delete" @click.stop="deleteDocument(doc.id)" title="Delete document">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Document Details Panel -->
      <aside v-if="selectedDocument" class="details-panel">
        <div class="panel-header">
          <h2>Document Details</h2>
          <button class="btn btn-ghost btn-icon" @click="selectedDocument = null">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="panel-content">
          <div class="detail-icon">{{ getFileIcon(selectedDocument.type) }}</div>
          <h3>{{ selectedDocument.name }}</h3>

          <div class="detail-section">
            <label>Collection</label>
            <span>{{ collections.find(c => c.id === selectedDocument?.collection)?.name }}</span>
          </div>

          <div class="detail-section">
            <label>File Type</label>
            <span class="file-type-badge">{{ selectedDocument.type.toUpperCase() }}</span>
          </div>

          <div class="detail-section">
            <label>Size</label>
            <span>{{ formatFileSize(selectedDocument.size) }}</span>
          </div>

          <div class="detail-section">
            <label>Chunks</label>
            <span>{{ selectedDocument.chunks }} chunks indexed</span>
          </div>

          <div class="detail-section">
            <label>Status</label>
            <span class="status-badge" :style="{ backgroundColor: getStatusColor(selectedDocument.status) + '20', color: getStatusColor(selectedDocument.status) }">
              {{ selectedDocument.status }}
            </span>
          </div>

          <div class="detail-section">
            <label>Uploaded</label>
            <span>{{ formatDate(selectedDocument.uploadedAt) }}</span>
          </div>

          <div v-if="selectedDocument.metadata" class="detail-section">
            <label>Metadata</label>
            <div class="metadata-list">
              <div v-for="(value, key) in selectedDocument.metadata" :key="key" class="metadata-item">
                <span class="meta-key">{{ key }}:</span>
                <span class="meta-value">{{ value }}</span>
              </div>
            </div>
          </div>

          <div class="panel-actions">
            <button class="btn btn-primary btn-block">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              Search in Document
            </button>
            <button class="btn btn-ghost btn-block">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              Download
            </button>
            <button class="btn btn-error btn-block" @click="deleteDocument(selectedDocument.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              Delete
            </button>
          </div>
        </div>
      </aside>
    </div>

    <!-- Add Document Modal -->
    <div v-if="showAddDocModal" class="modal-overlay" @click.self="showAddDocModal = false">
      <div class="modal add-doc-modal">
        <div class="modal-header">
          <h2>Add New Document</h2>
          <button class="btn btn-ghost btn-icon" @click="showAddDocModal = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="doc-title">Title <span class="required">*</span></label>
            <input
              id="doc-title"
              v-model="newDocTitle"
              type="text"
              placeholder="Document title"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label for="doc-content">Content <span class="required">*</span></label>
            <textarea
              id="doc-content"
              v-model="newDocContent"
              placeholder="Document content to index..."
              class="form-textarea"
              rows="8"
            ></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="doc-category">Category</label>
              <select id="doc-category" v-model="newDocCategory" class="form-input">
                <option value="">Select category</option>
                <option v-for="col in collections" :key="col.id" :value="col.id">
                  {{ col.name }}
                </option>
                <option value="user_uploads">User Uploads</option>
              </select>
            </div>
            <div class="form-group">
              <label for="doc-source">Source</label>
              <input
                id="doc-source"
                v-model="newDocSource"
                type="text"
                placeholder="e.g., research_paper, manual"
                class="form-input"
              />
            </div>
          </div>
          <div class="form-group">
            <label for="doc-tags">Tags (comma-separated)</label>
            <input
              id="doc-tags"
              v-model="newDocTags"
              type="text"
              placeholder="e.g., iot, security, zigbee"
              class="form-input"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="showAddDocModal = false">Cancel</button>
          <button
            class="btn btn-primary"
            :disabled="isAddingDoc || !newDocTitle.trim() || !newDocContent.trim()"
            @click="addDocumentViaApi"
          >
            {{ isAddingDoc ? 'Adding...' : 'Add Document' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-base {
  max-width: 1600px;
  margin: 0 auto;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-xl);
}

.header-title h1 {
  font-size: 1.75rem;
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
}

.header-title p {
  margin: 0;
  color: var(--text-secondary);
}

.header-stats {
  display: flex;
  gap: var(--spacing-xl);
}

.header-stat {
  text-align: center;
}

.header-stat .stat-value {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.header-stat .stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* Search Section */
.search-section {
  margin-bottom: var(--spacing-xl);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
}

.search-bar svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-bar input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 1rem;
  color: var(--text-primary);
  outline: none;
}

.search-bar input::placeholder {
  color: var(--text-muted);
}

/* Search Results */
.search-results {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.results-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.result-card {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.result-doc {
  font-weight: 600;
  color: var(--text-primary);
}

.result-similarity {
  font-size: 0.8rem;
  font-weight: 600;
}

.result-collection {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
}

.result-content {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 var(--spacing-sm) 0;
}

.result-metadata {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.metadata-tag {
  font-size: 0.7rem;
  padding: 2px 6px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

/* Content Layout */
.kb-content {
  display: grid;
  grid-template-columns: 280px 1fr auto;
  gap: var(--spacing-lg);
}

/* Collections Sidebar */
.collections-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  height: fit-content;
}

.collections-sidebar h2 {
  font-size: 1rem;
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--text-primary);
}

.collections-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.collection-card {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.collection-card:hover {
  border-color: var(--collection-color);
}

.collection-card.selected {
  border-color: var(--collection-color);
  background: linear-gradient(135deg, var(--bg-input), color-mix(in srgb, var(--collection-color) 10%, var(--bg-input)));
}

.collection-icon {
  font-size: 1.5rem;
}

.collection-info h3 {
  font-size: 0.9rem;
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
}

.collection-info p {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0 0 var(--spacing-xs) 0;
}

.collection-stats {
  display: flex;
  gap: var(--spacing-md);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

/* Documents Area */
.documents-area {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* Upload Zone */
.upload-zone {
  background: var(--bg-card);
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  text-align: center;
  transition: all var(--transition-fast);
}

.upload-zone.dragging {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.upload-zone svg {
  color: var(--text-muted);
  margin-bottom: var(--spacing-md);
}

.upload-zone p {
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-secondary);
}

.upload-link {
  color: var(--color-primary);
  cursor: pointer;
  text-decoration: underline;
}

.upload-hint {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.upload-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-md);
}

.progress-bar {
  width: 100%;
  max-width: 300px;
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
  transition: width var(--transition-fast);
}

/* Documents Section */
.documents-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.section-header h2 {
  font-size: 1rem;
  margin: 0;
  color: var(--text-primary);
}

.doc-count {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.documents-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.document-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.document-card:hover {
  border-color: var(--color-primary);
}

.document-card.selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.doc-icon {
  font-size: 1.5rem;
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-info h4 {
  font-size: 0.9rem;
  margin: 0 0 var(--spacing-xs) 0;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  display: flex;
  gap: var(--spacing-md);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.doc-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.75rem;
  text-transform: capitalize;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.doc-delete {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all var(--transition-fast);
}

.document-card:hover .doc-delete {
  opacity: 1;
}

.doc-delete:hover {
  background: var(--color-error);
  color: white;
}

/* Details Panel */
.details-panel {
  width: 300px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  height: fit-content;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.panel-header h2 {
  font-size: 1rem;
  margin: 0;
}

.panel-content {
  text-align: center;
}

.detail-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.panel-content h3 {
  font-size: 1rem;
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--text-primary);
  word-break: break-word;
}

.detail-section {
  text-align: left;
  margin-bottom: var(--spacing-md);
}

.detail-section label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.detail-section span {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.file-type-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.75rem !important;
  font-weight: 600;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem !important;
  font-weight: 600;
  text-transform: capitalize;
}

.metadata-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.metadata-item {
  display: flex;
  gap: var(--spacing-xs);
  font-size: 0.8rem;
}

.meta-key {
  color: var(--text-muted);
}

.meta-value {
  color: var(--text-secondary);
}

.panel-actions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xl);
}

.btn-block {
  width: 100%;
  justify-content: center;
}

.btn-error {
  background: var(--color-error);
  border-color: var(--color-error);
}

.btn-error:hover {
  opacity: 0.9;
}

/* Responsive */
@media (max-width: 1200px) {
  .kb-content {
    grid-template-columns: 1fr;
  }

  .collections-sidebar {
    order: 1;
  }

  .collections-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }

  .documents-area {
    order: 2;
  }

  .details-panel {
    width: 100%;
    order: 3;
  }
}

@media (max-width: 768px) {
  .kb-header {
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .header-stats {
    width: 100%;
    justify-content: space-around;
  }

  .search-bar {
    flex-wrap: wrap;
  }

  .search-bar input {
    width: 100%;
    order: -1;
  }

  .collections-list {
    grid-template-columns: 1fr;
  }
}

/* Header Actions */
.header-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-left: var(--spacing-lg);
}

.header-actions .btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.header-actions .btn svg {
  flex-shrink: 0;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Indexing Result */
.indexing-result {
  padding: var(--spacing-sm) var(--spacing-md);
  margin: var(--spacing-md) 0;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.9rem;
}

.indexing-result.success {
  background: rgba(34, 197, 94, 0.15);
  color: var(--color-success);
  border: 1px solid var(--color-success);
}

.indexing-result.error {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-error);
  border: 1px solid var(--color-error);
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
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.modal-body {
  padding: var(--spacing-lg);
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-group .required {
  color: var(--color-error);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.form-textarea {
  resize: vertical;
  min-height: 120px;
  font-family: inherit;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .header-actions {
    margin-left: 0;
    margin-top: var(--spacing-sm);
  }
}
</style>
