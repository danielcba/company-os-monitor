export type CognitiveFamily =
  | 'Perception'
  | 'Reasoning'
  | 'Action'
  | 'Learning'
  | 'Access'

export type PipelineConcept =
  | 'Observation'
  | 'Evidence'
  | 'Context'
  | 'Pattern'
  | 'Anomaly'
  | 'Hypothesis'
  | 'Insight'
  | 'Confidence'
  | 'Recommendation'
  | 'Decision'

export interface ServiceHealth {
  service: string
  url: string
  status: number
  healthy: boolean
  error?: string
}

export interface ServicesHealthResponse {
  services: ServiceHealth[]
}

export type CognitiveReportType = 'executive' | 'technical' | 'compliance' | 'json'

export interface CognitiveReport {
  id: string
  tenant_id: string
  report_type: CognitiveReportType
  title: string
  summary: string | null
  ai_generated: boolean
  model_used: string | null
  period_start: string | null
  period_end: string | null
  generated_at: string
  file_path: string | null
}

export interface CognitiveReportFacets {
  report_types: string[]
}

export interface CognitiveReportPage {
  reports: CognitiveReport[]
  total: number
  limit: number
  offset: number
  facets: CognitiveReportFacets
}

export type CognitiveReportSort = 'generated_at_desc' | 'generated_at_asc'

export interface CognitiveReportDetail {
  report: CognitiveReport & { content: Record<string, unknown> }
  tenant: { id: string; name: string; slug: string } | null
}

export interface CognitiveTotals {
  observations: number
  evidence: number
  contexts: number
  active_contexts: number
  patterns: number
  anomalies: number
  hypotheses: number
  confidence_scores: number
  recommendations: number
  decisions: number
  reports: number
  servers: number
}

export interface CognitiveStatusBreakdown {
  hypotheses: Record<string, number>
  recommendations: Record<string, number>
  decisions: Record<string, number>
}

export interface CognitiveSummary {
  tenant_id: string
  totals: CognitiveTotals
  status: CognitiveStatusBreakdown
}

export type QualityClass = 'Q1' | 'Q2' | 'Q3' | 'Q4'

export interface Observation {
  id: string
  tenant_id: string
  source_id: string
  source_type: string
  fact_type: string
  fact_value: Record<string, unknown>
  unit: string
  captured_at: string
  quality_class: QualityClass
  raw_payload: Record<string, unknown>
}

export interface ObservationsFacets {
  fact_types: string[]
  source_types: string[]
  quality_classes: QualityClass[]
}

export interface ObservationsPage {
  observations: Observation[]
  total: number
  limit: number
  offset: number
  facets: ObservationsFacets
}

export type ObservationSort = 'captured_at_desc' | 'captured_at_asc'

export interface Evidence {
  id: string
  tenant_id: string
  observation_ids: string[]
  organization_type: string
  description: string
  quality_class: QualityClass
  weight: number
  organized_at: string
}

export interface EvidenceFacets {
  organization_types: string[]
  quality_classes: QualityClass[]
}

export interface EvidencePage {
  evidence: Evidence[]
  total: number
  limit: number
  offset: number
  facets: EvidenceFacets
}

export type EvidenceSort = 'organized_at_desc' | 'organized_at_asc'

export interface EvidenceDetail {
  evidence: Evidence
  observations: Observation[]
}

export interface CompetingModel {
  mental_model_id: string
  coherence_score: number
}

export interface CognitiveContext {
  id: string
  tenant_id: string
  evidence_ids: string[]
  mental_model_id: string
  purpose: string
  coherence_score: number
  competing_models: CompetingModel[]
  activated_at: string
  is_active: boolean
}

export interface CognitiveContextFacets {
  purposes: string[]
  mental_model_ids: string[]
  is_active: string[]
}

export interface CognitiveContextPage {
  contexts: CognitiveContext[]
  total: number
  limit: number
  offset: number
  facets: CognitiveContextFacets
}

export type CognitiveContextSort = 'activated_at_desc' | 'activated_at_asc'

export interface CognitiveContextDetail {
  context: CognitiveContext
  evidence: Evidence[]
}

export interface CognitivePattern {
  id: string
  tenant_id: string
  context_id: string
  pattern_type: string
  description: string
  strength_measure: number
  frequency: string | null
  detected_at: string
  is_active: boolean
}

export interface CognitivePatternFacets {
  pattern_types: string[]
  is_active: string[]
}

export interface CognitivePatternPage {
  patterns: CognitivePattern[]
  total: number
  limit: number
  offset: number
  facets: CognitivePatternFacets
}

export type CognitivePatternSort = 'detected_at_desc' | 'detected_at_asc'

export interface CognitivePatternDetail {
  pattern: CognitivePattern
  context: CognitiveContext | null
}


export interface CognitiveAnomaly {
  id: string
  tenant_id: string
  context_id: string
  pattern_id: string | null
  anomaly_class: string
  deviation_score: number
  tolerance_threshold: number
  detected_at: string
}

export interface CognitiveAnomalyFacets {
  anomaly_classes: string[]
}

export interface CognitiveAnomalyPage {
  anomalies: CognitiveAnomaly[]
  total: number
  limit: number
  offset: number
  facets: CognitiveAnomalyFacets
}

export type CognitiveAnomalySort = 'detected_at_desc' | 'detected_at_asc'

export type CognitiveHypothesisStatus = 'candidate' | 'confirmed' | 'falsified'

export interface CognitiveHypothesis {
  id: string
  tenant_id: string
  anomaly_ids: string[]
  pattern_ids: string[]
  description: string
  predicted_consequences: string[]
  falsification_criterion: string
  coherence_score: number
  status: CognitiveHypothesisStatus
  generated_at: string
}

export interface CognitiveHypothesisFacets {
  statuses: string[]
}

export interface CognitiveHypothesisPage {
  hypotheses: CognitiveHypothesis[]
  total: number
  limit: number
  offset: number
  facets: CognitiveHypothesisFacets
}

export type CognitiveHypothesisSort = 'generated_at_desc' | 'generated_at_asc'

export type CognitiveConfidenceTargetType = 'hypothesis' | 'recommendation' | 'decision'

export interface CognitiveConfidence {
  id: string
  tenant_id: string
  target_type: CognitiveConfidenceTargetType
  target_id: string
  evidential_support: number
  explanatory_coherence: number
  historical_calibration: number
  confidence_score: number
  alpha: number
  calibration_justification: string
  calibration_error_estimate: number
  computed_at: string
}

export interface CognitiveConfidenceFacets {
  target_types: string[]
}

export interface CognitiveConfidencePage {
  confidence: CognitiveConfidence[]
  total: number
  limit: number
  offset: number
  facets: CognitiveConfidenceFacets
}

export type CognitiveConfidenceSort = 'computed_at_desc' | 'computed_at_asc'

export interface CognitiveConfidenceSummary {
  total: number
  by_target_type: Record<string, number>
  averages: {
    confidence: number
    support: number
    coherence: number
    historical_calibration: number
    ece: number
    alpha: number
  }
  range: {
    min_confidence: number
    max_confidence: number
  }
}

export interface CognitiveConfidenceDetail {
  confidence: CognitiveConfidence
  target: CognitiveHypothesisDetail | CognitiveDecision | CognitiveRecommendation | null
}

export interface CognitiveDecision {
  id: string
  tenant_id: string
  recommendation_id: string
  confidence_id: string
  authority_id: string
  commitment: string
  expected_outcomes: {
    prediction: string
    verifiable_by: string
    deadline: string
  }[]
  risk_tolerance: string
  status: string
  committed_at: string
  executed_at: string | null
  actual_outcomes: unknown[] | null
}

export type CognitiveDecisionStatus =
  | 'committed'
  | 'executing'
  | 'completed'
  | 'rolled_back'

export interface CognitiveDecisionFacets {
  statuses: string[]
}

export interface CognitiveDecisionPage {
  decisions: CognitiveDecision[]
  total: number
  limit: number
  offset: number
  facets: CognitiveDecisionFacets
}

export type CognitiveDecisionSort = 'committed_at_desc' | 'committed_at_asc'

export interface CognitiveDecisionDetail {
  decision: CognitiveDecision
  recommendation: CognitiveRecommendationDetail | null
  confidence: CognitiveConfidenceDetail | null
}

export interface CognitiveRecommendation {
  id: string
  tenant_id: string
  hypothesis_id: string
  insight_id?: string
  confidence_id: string
  action_description: string
  rationale: string
  expected_consequences: string[]
  alternatives_considered: { option?: string; not_chosen?: string }[]
  confidence_score: number
  status: string
  proposed_at: string
}

export type CognitiveRecommendationStatus =
  | 'proposed'
  | 'accepted'
  | 'rejected'
  | 'superseded'

export interface CognitiveRecommendationFacets {
  statuses: string[]
}

export interface CognitiveRecommendationPage {
  recommendations: CognitiveRecommendation[]
  total: number
  limit: number
  offset: number
  facets: CognitiveRecommendationFacets
}

export type CognitiveRecommendationSort = 'proposed_at_desc' | 'proposed_at_asc'

export interface CognitiveRecommendationDetail {
  recommendation: CognitiveRecommendation
  hypothesis: CognitiveHypothesisDetail | null
  confidence: CognitiveConfidenceDetail | null
}

export interface CognitiveHypothesisDetail {
  hypothesis: CognitiveHypothesis
  anomalies: CognitiveAnomaly[]
  patterns: CognitivePattern[]
  contexts: Record<string, CognitiveContext>
}

// ── Insights (Reasoning - Restructure) ───────────────────────────────────

export interface CognitiveInsight {
  id: string
  tenant_id: string
  context_id: string
  hypothesis_ids: string[]
  description: string
  prior_understanding: string | null
  mental_model_update: Record<string, unknown> | null
  generated_at: string
}

export interface CognitiveInsightFacets {
  hypothesis_ids: string[]
  context_ids: string[]
}

export interface CognitiveInsightPage {
  insights: CognitiveInsight[]
  total: number
  limit: number
  offset: number
  facets: CognitiveInsightFacets
}

export type CognitiveInsightSort = 'generated_at_desc' | 'generated_at_asc'

export interface CognitiveInsightDetail {
  insight: CognitiveInsight
  hypotheses: CognitiveHypothesis[]
  context: CognitiveContext | null
}

export type ApiState =
  | 'idle'
  | 'loading'
  | 'success'
  | 'error'
  | 'unauthorized'
  | 'forbidden'

export class ApiError extends Error {
  status: number
  code: 'unauthorized' | 'forbidden' | 'error'

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = status === 401 ? 'unauthorized' : status === 403 ? 'forbidden' : 'error'
  }
}

// ── Audit Log (Episodic Memory) ──────────────────────────────────────────

export type CognitiveLayer = 'perception' | 'reasoning' | 'confidence' | 'action' | 'memory'

export type AuditConcept =
  | 'observation'
  | 'evidence'
  | 'context'
  | 'pattern'
  | 'anomaly'
  | 'hypothesis'
  | 'insight'
  | 'confidence'
  | 'recommendation'
  | 'decision'

export type AuditAction =
  | 'captured'
  | 'organized'
  | 'activated'
  | 'detected'
  | 'generated'
  | 'restructured'
  | 'calibrated'
  | 'proposed'
  | 'committed'
  | 'executed'

export interface AuditLogEntry {
  id: string
  tenant_id: string
  user_id: string | null
  policy_id: string | null
  cognitive_layer: CognitiveLayer
  cognitive_concept: AuditConcept
  action: AuditAction
  resource_type: string
  resource_id: string
  details: Record<string, unknown> | null
  ip_address: string | null
  user_agent: string | null
  timestamp: string
}

export interface AuditLogFacets {
  cognitive_layers: string[]
  cognitive_concepts: string[]
  actions: string[]
}

export interface AuditLogPage {
  entries: AuditLogEntry[]
  total: number
  limit: number
  offset: number
  facets: AuditLogFacets
}

export type AuditLogSort = 'timestamp_desc' | 'timestamp_asc'

// ── Tenants (Administration) ─────────────────────────────────────────────

export interface Tenant {
  id: string
  name: string
  slug: string
  plan: string
  settings: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface TenantsPage {
  tenants: Tenant[]
}

// ── Notifications ────────────────────────────────────────────────────────

export type NotificationType = 'anomaly' | 'decision' | 'system' | 'calibration'
export type NotificationSeverity = 'critical' | 'warning' | 'info'

export interface Notification {
  id: string
  type: NotificationType
  severity: NotificationSeverity
  title: string
  message: string
  timestamp: string
  read: boolean
  link?: string
}