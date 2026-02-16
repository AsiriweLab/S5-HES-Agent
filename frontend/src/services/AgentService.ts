/**
 * AgentService - Frontend service for interacting with AI agents
 * Provides methods for threat scenario generation, home configuration assistance,
 * and other AI-powered features via the backend orchestrator
 *
 * RESEARCH INTEGRITY: This service has NO synthetic fallbacks.
 * All methods require the LLM backend to be available.
 * If the LLM is unavailable, operations will fail with clear errors.
 */

import axios from 'axios'

// ============== TYPES ==============

export type AgentTaskType =
  | 'generate_threats'
  | 'analyze_scenario'
  | 'suggest_defenses'
  | 'build_attack_chain'
  | 'create_home'
  | 'validate_configuration'

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export interface AgentTask {
  id: string
  type: AgentTaskType
  prompt: string
  status: TaskStatus
  result?: unknown
  error?: string
  createdAt: Date
  completedAt?: Date
}

export interface ThreatGenerationRequest {
  homeType: string
  deviceTypes: string[]
  securityLevel: 'low' | 'medium' | 'high'
  attackDifficulty: 'beginner' | 'intermediate' | 'advanced' | 'expert'
  targetCategory?: string
  duration?: number // simulation duration in minutes
  numEvents?: number // number of threat events to generate
}

export interface GeneratedThreatEvent {
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
}

export interface ThreatGenerationResponse {
  success: boolean
  events: GeneratedThreatEvent[]
  attackChainDescription?: string
  mitreTechniques: string[]
  estimatedDuration: number
  message?: string
}

export interface DefenseSuggestion {
  id: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  mitigates: string[] // threat types this defense mitigates
  implementationSteps: string[]
  estimatedEffort: string
}

export interface ScenarioAnalysis {
  summary: string
  riskScore: number
  vulnerabilities: string[]
  attackPaths: string[]
  recommendations: DefenseSuggestion[]
  mitreCoverage: string[]
}

// ============== SERVICE CLASS ==============

class AgentService {
  private baseUrl = '/api'

  /**
   * Check if the LLM service is available
   */
  async checkLLMHealth(): Promise<boolean> {
    try {
      const response = await axios.get(`${this.baseUrl}/chat/health`)
      return response.data.ollama_available === true
    } catch {
      return false
    }
  }

  /**
   * Ensure LLM is available, throw if not
   */
  private async requireLLM(): Promise<void> {
    const available = await this.checkLLMHealth()
    if (!available) {
      throw new Error(
        'LLM service is unavailable. Please ensure Ollama is running. ' +
        'This operation requires a live LLM connection - no synthetic fallback is available.'
      )
    }
  }

  /**
   * Generate threat events using AI
   *
   * RESEARCH INTEGRITY: This method requires LLM to be available.
   * No synthetic fallback - if LLM is unavailable, the operation fails.
   */
  async generateThreats(request: ThreatGenerationRequest): Promise<ThreatGenerationResponse> {
    await this.requireLLM()

    const prompt = this.buildThreatPrompt(request)

    try {
      // LLM generation can take 30-60+ seconds, so we need a long timeout
      const response = await axios.post(
        `${this.baseUrl}/chat/`,
        {
          message: prompt,
          session_id: `threat-gen-${Date.now()}`,
          use_rag: true,
          temperature: 0.7,
          max_tokens: 2048,
        },
        {
          timeout: 120000, // 2 minute timeout for LLM generation
        }
      )

      // Parse the AI response into structured threat events
      return this.parseThreatResponse(response.data.message, request)
    } catch (error) {
      console.error('LLM threat generation failed:', error)
      throw new Error(
        'Failed to generate threats using LLM. Please check that Ollama is running and try again.'
      )
    }
  }

  /**
   * Generate a multi-stage attack chain
   *
   * RESEARCH INTEGRITY: This method requires LLM to be available.
   * No synthetic fallback - if LLM is unavailable, the operation fails.
   */
  async generateAttackChain(
    homeConfig: { devices: string[]; rooms: string[] },
    objective: string
  ): Promise<ThreatGenerationResponse> {
    await this.requireLLM()

    const prompt = `Generate a realistic multi-stage attack chain for a smart home with the following configuration:

Devices: ${homeConfig.devices.join(', ')}
Rooms: ${homeConfig.rooms.join(', ')}

Attack Objective: ${objective}

Create a sequence of 3-5 coordinated attack events that form a coherent attack chain. Each event should:
1. Build upon the previous stage
2. Have realistic timing and dependencies
3. Include MITRE ATT&CK technique references
4. Target specific devices in the home

Format the response as JSON with this structure:
{
  "description": "Overall attack chain description",
  "stages": [
    {
      "type": "attack_type",
      "name": "Stage name",
      "description": "What happens in this stage",
      "severity": "low|medium|high|critical",
      "severityValue": 0-100,
      "duration": minutes,
      "mitreTechnique": "T1XXX",
      "indicators": ["indicator1", "indicator2"],
      "targetDevices": ["device1"],
      "successProbability": 0-100
    }
  ]
}`

    try {
      const response = await axios.post(
        `${this.baseUrl}/chat/`,
        {
          message: prompt,
          session_id: `attack-chain-${Date.now()}`,
          use_rag: true,
          temperature: 0.7,
        },
        {
          timeout: 120000, // 2 minute timeout for LLM generation
        }
      )

      return this.parseAttackChainResponse(response.data.message)
    } catch (error) {
      console.error('LLM attack chain generation failed:', error)
      throw new Error(
        'Failed to generate attack chain using LLM. Please check that Ollama is running and try again.'
      )
    }
  }

  /**
   * Analyze a threat scenario and provide insights
   */
  async analyzeScenario(events: GeneratedThreatEvent[]): Promise<ScenarioAnalysis> {
    await this.requireLLM()

    const eventSummary = events.map(e => `${e.name} (${e.type}, ${e.severity})`).join('\n')

    const prompt = `Analyze the following smart home attack scenario:

${eventSummary}

Provide a JSON response with this structure:
{
  "summary": "Brief summary of the overall attack",
  "riskScore": 1-100,
  "vulnerabilities": ["vuln1", "vuln2"],
  "attackPaths": ["path1", "path2"],
  "recommendations": [
    {
      "id": "def-1",
      "title": "Defense title",
      "description": "What to do",
      "priority": "critical|high|medium|low",
      "mitigates": ["threat_type1"],
      "implementationSteps": ["step1", "step2"],
      "estimatedEffort": "easy|moderate|complex"
    }
  ],
  "mitreCoverage": ["T1557", "T1040"]
}`

    try {
      const response = await axios.post(`${this.baseUrl}/chat/`, {
        message: prompt,
        session_id: `analysis-${Date.now()}`,
        use_rag: true,
      })

      return this.parseAnalysisResponse(response.data.message)
    } catch (error) {
      console.error('Failed to analyze scenario:', error)
      throw new Error(
        'Failed to analyze scenario using LLM. Please check that Ollama is running and try again.'
      )
    }
  }

  /**
   * Get defense suggestions for a threat scenario
   */
  async suggestDefenses(events: GeneratedThreatEvent[]): Promise<DefenseSuggestion[]> {
    await this.requireLLM()

    const threatTypes = [...new Set(events.map(e => e.type))]

    const prompt = `Suggest security defenses for a smart home facing these threat types:

${threatTypes.join(', ')}

Provide a JSON array of defenses with this structure:
[
  {
    "id": "def-1",
    "title": "Defense title",
    "description": "What this defense does",
    "priority": "critical|high|medium|low",
    "mitigates": ["threat_type1", "threat_type2"],
    "implementationSteps": ["step1", "step2", "step3"],
    "estimatedEffort": "easy|moderate|complex"
  }
]`

    try {
      const response = await axios.post(`${this.baseUrl}/chat/`, {
        message: prompt,
        session_id: `defense-${Date.now()}`,
        use_rag: true,
      })

      return this.parseDefenseResponse(response.data.message)
    } catch (error) {
      console.error('Failed to suggest defenses:', error)
      throw new Error(
        'Failed to get defense suggestions using LLM. Please check that Ollama is running and try again.'
      )
    }
  }

  /**
   * Stream threat generation for real-time UI updates
   */
  async *streamThreatGeneration(
    request: ThreatGenerationRequest
  ): AsyncGenerator<{ type: 'progress' | 'event' | 'done'; data: unknown }> {
    await this.requireLLM()

    const prompt = this.buildThreatPrompt(request)

    try {
      const response = await fetch(`${this.baseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: prompt,
          session_id: `threat-stream-${Date.now()}`,
          use_rag: true,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value)
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.content) {
                yield { type: 'progress', data: data.content }
              }
              if (data.done) {
                yield { type: 'done', data: data }
              }
            } catch {
              // Skip non-JSON lines
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error)
      yield { type: 'done', data: { error: error instanceof Error ? error.message : 'Unknown error' } }
    }
  }

  // ============== PRIVATE HELPERS ==============

  private buildThreatPrompt(request: ThreatGenerationRequest): string {
    return `Generate ${request.numEvents || 5} realistic IoT security threat events for a smart home simulation.

Home Configuration:
- Home Type: ${request.homeType}
- Devices: ${request.deviceTypes.join(', ')}
- Security Level: ${request.securityLevel}

Attack Requirements:
- Difficulty Level: ${request.attackDifficulty}
${request.targetCategory ? `- Target Category: ${request.targetCategory}` : ''}
- Simulation Duration: ${request.duration || 480} minutes

Provide the response as JSON with this structure:
{
  "events": [
    {
      "type": "attack_type",
      "name": "Attack name",
      "description": "What happens",
      "startTime": minutes_from_start,
      "duration": minutes,
      "severity": "low|medium|high|critical",
      "severityValue": 1-100,
      "difficulty": 1-100,
      "targetDevices": ["device1", "device2"],
      "attackVector": "T1XXX",
      "indicators": ["indicator1", "indicator2"]
    }
  ],
  "mitreTechniques": ["T1557", "T1078"],
  "attackChainDescription": "Overall description"
}`
  }

  private parseThreatResponse(
    message: string,
    request: ThreatGenerationRequest
  ): ThreatGenerationResponse {
    // Try to extract JSON from the response
    const jsonMatch = message.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0])
        if (parsed.events && Array.isArray(parsed.events)) {
          return {
            success: true,
            events: parsed.events.map((e: Record<string, unknown>, i: number) => ({
              id: `llm-${Date.now()}-${i}`,
              type: e.type || 'unknown',
              name: e.name || `Attack ${i + 1}`,
              startTime: e.startTime || i * 60,
              duration: e.duration || 15,
              severity: e.severity || 'medium',
              severityValue: e.severityValue || 50,
              difficulty: e.difficulty || 50,
              targetDevices: e.targetDevices || [],
              description: e.description || '',
              attackVector: e.attackVector || '',
              indicators: e.indicators || [],
            })),
            mitreTechniques: parsed.mitreTechniques || [],
            estimatedDuration: request.duration || 480,
            attackChainDescription: parsed.attackChainDescription || 'LLM-generated threat scenario',
          }
        }
      } catch (e) {
        console.warn('Failed to parse JSON from LLM response:', e)
      }
    }

    // If JSON parsing failed, throw error - no fallback to fake data
    throw new Error(
      'Failed to parse LLM response into structured threat data. ' +
      'The LLM response was not in the expected JSON format.'
    )
  }

  private parseAttackChainResponse(message: string): ThreatGenerationResponse {
    // Try to extract JSON from the response
    const jsonMatch = message.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0])
        if (parsed.stages && Array.isArray(parsed.stages)) {
          const events: GeneratedThreatEvent[] = []
          const mitreTechniques: string[] = []
          let startTime = 30

          parsed.stages.forEach((stage: Record<string, unknown>, i: number) => {
            const event: GeneratedThreatEvent = {
              id: `chain-llm-${Date.now()}-${i}`,
              type: (stage.type as string) || 'unknown',
              name: (stage.name as string) || `Stage ${i + 1}`,
              startTime,
              duration: (stage.duration as number) || 20,
              severity: (stage.severity as 'low' | 'medium' | 'high' | 'critical') || 'medium',
              severityValue: (stage.severityValue as number) || 50,
              difficulty: 30 + i * 15,
              targetDevices: (stage.targetDevices as string[]) || [],
              description: (stage.description as string) || '',
              attackVector: (stage.mitreTechnique as string) || '',
              indicators: (stage.indicators as string[]) || [],
              stageNumber: i + 1,
              dependsOn: i > 0 ? [events[i - 1].id] : undefined,
              successProbability: (stage.successProbability as number) || 70,
            }

            events.push(event)
            if (stage.mitreTechnique) {
              mitreTechniques.push(stage.mitreTechnique as string)
            }
            startTime += event.duration + 15
          })

          return {
            success: true,
            events,
            mitreTechniques: [...new Set(mitreTechniques)],
            estimatedDuration: startTime + 30,
            attackChainDescription: (parsed.description as string) || 'LLM-generated attack chain',
          }
        }
      } catch (e) {
        console.warn('Failed to parse JSON from LLM response:', e)
      }
    }

    // If JSON parsing failed, throw error - no fallback to fake data
    throw new Error(
      'Failed to parse LLM response into structured attack chain data. ' +
      'The LLM response was not in the expected JSON format.'
    )
  }

  private parseAnalysisResponse(message: string): ScenarioAnalysis {
    // Try to extract JSON from the response
    const jsonMatch = message.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0])
        return {
          summary: parsed.summary || '',
          riskScore: parsed.riskScore || 0,
          vulnerabilities: parsed.vulnerabilities || [],
          attackPaths: parsed.attackPaths || [],
          recommendations: (parsed.recommendations || []).map((r: Record<string, unknown>) => ({
            id: r.id || `def-${Date.now()}`,
            title: r.title || '',
            description: r.description || '',
            priority: r.priority || 'medium',
            mitigates: r.mitigates || [],
            implementationSteps: r.implementationSteps || [],
            estimatedEffort: r.estimatedEffort || 'moderate',
          })),
          mitreCoverage: parsed.mitreCoverage || [],
        }
      } catch (e) {
        console.warn('Failed to parse JSON from LLM response:', e)
      }
    }

    // If JSON parsing failed, throw error - no fallback to fake data
    throw new Error(
      'Failed to parse LLM response into scenario analysis. ' +
      'The LLM response was not in the expected JSON format.'
    )
  }

  private parseDefenseResponse(message: string): DefenseSuggestion[] {
    // Try to extract JSON array from the response
    const jsonMatch = message.match(/\[[\s\S]*\]/)
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0])
        if (Array.isArray(parsed)) {
          return parsed.map((d: Record<string, unknown>) => ({
            id: (d.id as string) || `def-${Date.now()}`,
            title: (d.title as string) || '',
            description: (d.description as string) || '',
            priority: (d.priority as 'low' | 'medium' | 'high' | 'critical') || 'medium',
            mitigates: (d.mitigates as string[]) || [],
            implementationSteps: (d.implementationSteps as string[]) || [],
            estimatedEffort: (d.estimatedEffort as string) || 'moderate',
          }))
        }
      } catch (e) {
        console.warn('Failed to parse JSON from LLM response:', e)
      }
    }

    // If JSON parsing failed, throw error - no fallback to fake data
    throw new Error(
      'Failed to parse LLM response into defense suggestions. ' +
      'The LLM response was not in the expected JSON format.'
    )
  }
}

// Export singleton instance
export const agentService = new AgentService()