/**
 * Human Review Queue API Service
 *
 * Provides methods for interacting with the review queue API
 * for anti-hallucination verification flagged items.
 */

import axios from 'axios'

const API_BASE = 'http://localhost:8000'

// Types
export type ReviewItemStatus = 'pending' | 'approved' | 'rejected' | 'modified'
export type ReviewItemType =
  | 'llm_response'
  | 'agent_output'
  | 'rag_result'
  | 'home_config'
  | 'threat_scenario'
  | 'simulation_result'

export interface FlaggedCheck {
  category: string
  name: string
  message: string
  confidence: number
}

export interface ReviewItem {
  item_id: string
  item_type: ReviewItemType
  status: ReviewItemStatus
  content: unknown
  content_summary: string
  confidence_score: number
  verification_status: string
  flagged_checks: FlaggedCheck[]
  review_reasons: string[]
  created_at: string
  reviewed_at?: string
  reviewer_notes?: string
  modified_content?: unknown
  source_agent?: string
  session_id?: string
  request_context?: string
}

export interface ReviewDecision {
  decision: ReviewItemStatus
  notes?: string
  modified_content?: unknown
}

export interface ReviewQueueStats {
  total_items: number
  pending_items: number
  approved_items: number
  rejected_items: number
  modified_items: number
  avg_confidence: number
  oldest_pending_age_seconds?: number
}

export interface ReviewQueueSettings {
  auto_approve_threshold: number
  auto_reject_threshold: number
  max_queue_size: number
  strict_mode: boolean
}

// API Functions
export const reviewApi = {
  /**
   * Get pending items in the review queue
   */
  async getQueue(limit: number = 20): Promise<ReviewItem[]> {
    const response = await axios.get(`${API_BASE}/api/review/queue`, {
      params: { limit },
    })
    return response.data
  },

  /**
   * Get a specific review item by ID
   */
  async getItem(itemId: string): Promise<ReviewItem> {
    const response = await axios.get(`${API_BASE}/api/review/queue/${itemId}`)
    return response.data
  },

  /**
   * Submit a review decision for an item
   */
  async submitReview(itemId: string, decision: ReviewDecision): Promise<ReviewItem> {
    const response = await axios.post(`${API_BASE}/api/review/queue/${itemId}/review`, decision)
    return response.data
  },

  /**
   * Get queue statistics
   */
  async getStats(): Promise<ReviewQueueStats> {
    const response = await axios.get(`${API_BASE}/api/review/stats`)
    return response.data
  },

  /**
   * Get queue settings
   */
  async getSettings(): Promise<ReviewQueueSettings> {
    const response = await axios.get(`${API_BASE}/api/review/settings`)
    return response.data
  },

  /**
   * Update queue settings
   */
  async updateSettings(settings: ReviewQueueSettings): Promise<ReviewQueueSettings> {
    const response = await axios.put(`${API_BASE}/api/review/settings`, settings)
    return response.data
  },

  /**
   * Get recently reviewed items
   */
  async getReviewedItems(limit: number = 20): Promise<ReviewItem[]> {
    const response = await axios.get(`${API_BASE}/api/review/reviewed`, {
      params: { limit },
    })
    return response.data
  },

  /**
   * Clear reviewed items history
   */
  async clearReviewedItems(): Promise<{ message: string }> {
    const response = await axios.delete(`${API_BASE}/api/review/reviewed`)
    return response.data
  },

  /**
   * Add a sample review item (for testing)
   */
  async addSampleItem(): Promise<{ message: string; item_id?: string }> {
    const response = await axios.post(`${API_BASE}/api/review/test/add-sample`)
    return response.data
  },

  /**
   * Check if review API is available
   */
  async checkAvailability(): Promise<boolean> {
    try {
      await axios.get(`${API_BASE}/api/review/stats`, { timeout: 3000 })
      return true
    } catch {
      return false
    }
  },
}

export default reviewApi
