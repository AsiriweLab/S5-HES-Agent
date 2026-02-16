/**
 * RAG API Service
 *
 * Connects frontend Knowledge Base to backend RAG system.
 */

const API_BASE = 'http://localhost:8000/api/rag'

// Types matching backend models
export interface SearchRequest {
  query: string
  n_results?: number
  category?: string
}

export interface SearchResultItem {
  doc_id: string
  content: string
  title?: string
  category?: string
  source?: string
  similarity_score: number
  is_above_threshold: boolean
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
  total_results: number
  query_time_ms: number
}

export interface RAGContextRequest {
  query: string
  n_results?: number
}

export interface RAGContextResponse {
  query: string
  contexts: string[]
  sources: string[]
  confidence_scores: number[]
  formatted_context: string
  has_context: boolean
  retrieval_time_ms: number
}

export interface DocumentCreate {
  title: string
  content: string
  category?: string
  source: string
  tags?: string[]
}

export interface DocumentResponse {
  doc_id: string
  title: string
  content: string
  category: string
  source: string
  tags: string[]
  created_at: string
}

export interface KnowledgeBaseStats {
  collection_name: string
  document_count: number
  persist_directory: string
  embedding_model: string
  similarity_threshold: number
  knowledge_base_path: string
  // Text chunking settings (added for S2.5)
  chunking_enabled?: boolean
  chunk_size?: number
  chunk_overlap?: number
  // PDF parser availability (added for S2.7)
  pdf_parser_available?: boolean
  pdf_parser?: string | null
}

export interface CollectionStatsItem {
  collection_name: string
  document_count: number
  chunk_count: number
  categories: string[]
  sources: string[]
  date_range?: { start: string; end: string }
}

export interface ComprehensiveStats {
  total_documents: number
  total_chunks: number
  persist_directory: string
  embedding_model: string
  similarity_threshold: number
  collections: CollectionStatsItem[]
  adapters: Record<string, { status: string; sources: string[] }>
  keyword_index: Record<string, unknown>
  last_ingestion?: string
  uptime_seconds: number
}

export interface HybridSearchRequest {
  query: string
  collection?: string
  n_results?: number
  mode?: 'semantic_only' | 'keyword_only' | 'hybrid' | 'auto'
  fusion_method?: 'rrf' | 'weighted_sum' | 'max_score' | 'interleave'
}

export interface HybridSearchResultItem {
  document_id: string
  content: string
  score: number
  source: string
  metadata: Record<string, unknown>
  highlights: string[]
}

export interface HybridSearchResponse {
  query: string
  results: HybridSearchResultItem[]
  mode_used: string
  semantic_count: number
  keyword_count: number
  fusion_method: string
  total_candidates: number
  execution_time_ms: number
}

export interface IngestRequest {
  directory?: string
  recursive?: boolean
}

export interface IngestResponse {
  documents_ingested: number
  source_directory: string
}

// ===========================================================================
// Academic Paper Integration Types
// ===========================================================================

export interface AcademicSearchRequest {
  query: string
  sources?: string[]
  limit_per_source?: number
  from_year?: number
  ingest_to_kb?: boolean
}

export interface AcademicPaperItem {
  paper_id: string
  title: string
  abstract: string
  authors: string
  year?: number
  venue?: string
  source: string
  doi?: string
  arxiv_id?: string
  url?: string
  citations_count: number
  keywords: string[]
}

export interface AcademicSearchResponse {
  query: string
  papers: AcademicPaperItem[]
  total_results: number
  sources_searched: string[]
  papers_ingested: number
  adapter_stats: Record<string, unknown>
}

export interface AcademicIngestRequest {
  paper_ids: string[]
}

export interface AcademicIngestResponse {
  papers_ingested: number
  doc_ids: string[]
  failed: string[]
}

// ===========================================================================
// KB Versioning Types
// ===========================================================================

export interface CreateVersionRequest {
  name: string
  description?: string
  tags?: string[]
}

export interface VersionResponse {
  version_id: string
  version_number: number
  name: string
  description: string
  created_at: string
  created_by: string
  document_count: number
  hash: string
  parent_version?: string
  tags: string[]
}

export interface ChangeLogEntry {
  change_id: string
  change_type: string
  timestamp: string
  doc_id?: string
  doc_ids: string[]
  user: string
  description: string
}

export interface VersionDiffResponse {
  version_a: string
  version_b: string
  documents_added: string[]
  documents_removed: string[]
  documents_modified: string[]
  added_count: number
  removed_count: number
  modified_count: number
}

export interface VersioningStats {
  total_versions: number
  current_version?: string
  version_counter: number
  change_log_size: number
  snapshots_count: number
  data_dir: string
}

// ===========================================================================
// Advanced Reasoning Types
// ===========================================================================

export type ReasoningStrategy =
  | 'direct'
  | 'chain_of_thought'
  | 'multi_hop'
  | 'iterative'
  | 'hypothesis_driven'
  | 'comparative'
  | 'decomposition'

export interface ReasoningRequest {
  query: string
  strategy?: ReasoningStrategy
  n_results?: number
  include_trace?: boolean
}

export interface ReasoningStepResponse {
  step_number: number
  step_type: string
  thought: string
  action: string
  observation: string
  confidence: number
  sources: string[]
}

export interface ReasoningResponse {
  result_id: string
  query: string
  strategy: string
  answer: string
  confidence: number
  reasoning_trace?: ReasoningStepResponse[]
  sources: string[]
  contexts_count: number
  execution_time_ms: number
}

export interface ReasoningStrategies {
  strategies: Record<string, string>
  default: string
}

export interface ReasoningStats {
  total_reasoning_tasks: number
  successful_tasks: number
  average_steps: number
  average_confidence: number
  strategy_usage: Record<string, number>
}

// API Functions
class RAGApiService {
  private isAvailable = false
  private lastCheck = 0
  private checkInterval = 30000 // Check every 30 seconds

  /**
   * Check if RAG API is available
   */
  async checkAvailability(): Promise<boolean> {
    const now = Date.now()
    if (now - this.lastCheck < this.checkInterval && this.lastCheck > 0) {
      return this.isAvailable
    }

    try {
      const response = await fetch(`${API_BASE}/stats`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })
      this.isAvailable = response.ok
    } catch {
      this.isAvailable = false
    }

    this.lastCheck = now
    return this.isAvailable
  }

  /**
   * Search the knowledge base
   */
  async search(request: SearchRequest): Promise<SearchResponse> {
    const response = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        n_results: request.n_results ?? 5,
        category: request.category,
      }),
    })

    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get RAG context for LLM augmentation
   */
  async getContext(request: RAGContextRequest): Promise<RAGContextResponse> {
    const response = await fetch(`${API_BASE}/context`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        n_results: request.n_results ?? 5,
      }),
    })

    if (!response.ok) {
      throw new Error(`Context retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Perform hybrid search (semantic + keyword)
   */
  async hybridSearch(request: HybridSearchRequest): Promise<HybridSearchResponse> {
    const response = await fetch(`${API_BASE}/hybrid-search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        collection: request.collection ?? 'default',
        n_results: request.n_results ?? 10,
        mode: request.mode ?? 'auto',
        fusion_method: request.fusion_method ?? 'rrf',
      }),
    })

    if (!response.ok) {
      throw new Error(`Hybrid search failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Add a document to the knowledge base
   */
  async addDocument(document: DocumentCreate): Promise<DocumentResponse> {
    const response = await fetch(`${API_BASE}/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(document),
    })

    if (!response.ok) {
      throw new Error(`Document creation failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Add multiple documents in batch
   */
  async addDocumentsBatch(
    documents: DocumentCreate[]
  ): Promise<{ documents_created: number; doc_ids: string[] }> {
    const response = await fetch(`${API_BASE}/documents/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(documents),
    })

    if (!response.ok) {
      throw new Error(`Batch document creation failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Ingest documents from a directory
   */
  async ingestDirectory(request: IngestRequest = {}): Promise<IngestResponse> {
    const response = await fetch(`${API_BASE}/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        directory: request.directory,
        recursive: request.recursive ?? true,
      }),
    })

    if (!response.ok) {
      throw new Error(`Ingestion failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get basic knowledge base statistics
   */
  async getStats(): Promise<KnowledgeBaseStats> {
    const response = await fetch(`${API_BASE}/stats`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get comprehensive knowledge base statistics
   */
  async getComprehensiveStats(): Promise<ComprehensiveStats> {
    const response = await fetch(`${API_BASE}/stats/comprehensive`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Comprehensive stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * List available collections
   */
  async listCollections(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/collections`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Collections list failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get stats for a specific collection
   */
  async getCollectionStats(collectionName: string): Promise<CollectionStatsItem> {
    const response = await fetch(`${API_BASE}/collections/${collectionName}/stats`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Collection stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Reset the knowledge base (WARNING: deletes all data!)
   */
  async reset(): Promise<{ status: string; message: string }> {
    const response = await fetch(`${API_BASE}/reset`, {
      method: 'DELETE',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Reset failed: ${response.statusText}`)
    }

    return response.json()
  }

  // ===========================================================================
  // Academic Paper Integration Methods
  // ===========================================================================

  /**
   * Search for academic papers across multiple sources
   */
  async searchAcademicPapers(request: AcademicSearchRequest): Promise<AcademicSearchResponse> {
    const response = await fetch(`${API_BASE}/academic/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        sources: request.sources ?? ['arxiv', 'semantic_scholar'],
        limit_per_source: request.limit_per_source ?? 5,
        from_year: request.from_year,
        ingest_to_kb: request.ingest_to_kb ?? false,
      }),
    })

    if (!response.ok) {
      throw new Error(`Academic search failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Search all available academic sources
   */
  async searchAllAcademicSources(
    query: string,
    limit?: number,
    fromYear?: number,
    ingest?: boolean
  ): Promise<AcademicSearchResponse> {
    const params = new URLSearchParams({ query })
    if (limit) params.append('limit', String(limit))
    if (fromYear) params.append('from_year', String(fromYear))
    if (ingest) params.append('ingest', String(ingest))

    const response = await fetch(`${API_BASE}/academic/search-all?${params}`, {
      method: 'POST',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Academic search-all failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Ingest specific papers into the knowledge base
   */
  async ingestAcademicPapers(paperIds: string[]): Promise<AcademicIngestResponse> {
    const response = await fetch(`${API_BASE}/academic/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ paper_ids: paperIds }),
    })

    if (!response.ok) {
      throw new Error(`Academic paper ingestion failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * List available academic sources
   */
  async listAcademicSources(): Promise<string[]> {
    const response = await fetch(`${API_BASE}/academic/sources`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Academic sources list failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get academic adapter statistics
   */
  async getAcademicStats(): Promise<Record<string, unknown>> {
    const response = await fetch(`${API_BASE}/academic/stats`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Academic stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  // ===========================================================================
  // KB Versioning Methods
  // ===========================================================================

  /**
   * Create a new version of the knowledge base
   */
  async createVersion(request: CreateVersionRequest): Promise<VersionResponse> {
    const response = await fetch(`${API_BASE}/versions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        name: request.name,
        description: request.description ?? '',
        tags: request.tags ?? [],
      }),
    })

    if (!response.ok) {
      throw new Error(`Version creation failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * List all knowledge base versions
   */
  async listVersions(limit?: number, tag?: string): Promise<VersionResponse[]> {
    const params = new URLSearchParams()
    if (limit) params.append('limit', String(limit))
    if (tag) params.append('tag', tag)

    const url = params.toString() ? `${API_BASE}/versions?${params}` : `${API_BASE}/versions`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Version list failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get the current active version
   */
  async getCurrentVersion(): Promise<VersionResponse | null> {
    const response = await fetch(`${API_BASE}/versions/current`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Current version retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get a specific version by ID
   */
  async getVersion(versionId: string): Promise<VersionResponse> {
    const response = await fetch(`${API_BASE}/versions/${versionId}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Version retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Create a snapshot for a version
   */
  async createSnapshot(versionId: string): Promise<{ message: string; version_id: string; document_count: number }> {
    const response = await fetch(`${API_BASE}/versions/${versionId}/snapshot`, {
      method: 'POST',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Snapshot creation failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Compare two versions
   */
  async diffVersions(versionA: string, versionB: string): Promise<VersionDiffResponse> {
    const response = await fetch(`${API_BASE}/versions/diff/${versionA}/${versionB}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Version diff failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get change log
   */
  async getChangeLog(limit?: number, changeType?: string): Promise<ChangeLogEntry[]> {
    const params = new URLSearchParams()
    if (limit) params.append('limit', String(limit))
    if (changeType) params.append('change_type', changeType)

    const url = params.toString() ? `${API_BASE}/changelog?${params}` : `${API_BASE}/changelog`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Change log retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get versioning statistics
   */
  async getVersioningStats(): Promise<VersioningStats> {
    const response = await fetch(`${API_BASE}/versions/stats`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Versioning stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }

  // ===========================================================================
  // Advanced Reasoning Methods
  // ===========================================================================

  /**
   * Execute advanced reasoning over the knowledge base
   */
  async reasoningQuery(request: ReasoningRequest): Promise<ReasoningResponse> {
    const response = await fetch(`${API_BASE}/reasoning/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: request.query,
        strategy: request.strategy,
        n_results: request.n_results ?? 5,
        include_trace: request.include_trace ?? true,
      }),
    })

    if (!response.ok) {
      throw new Error(`Reasoning query failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * List available reasoning strategies
   */
  async listReasoningStrategies(): Promise<ReasoningStrategies> {
    const response = await fetch(`${API_BASE}/reasoning/strategies`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Reasoning strategies list failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get reasoning engine statistics
   */
  async getReasoningStats(): Promise<ReasoningStats> {
    const response = await fetch(`${API_BASE}/reasoning/stats`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    })

    if (!response.ok) {
      throw new Error(`Reasoning stats retrieval failed: ${response.statusText}`)
    }

    return response.json()
  }
}

// Export singleton instance
export const ragApi = new RAGApiService()