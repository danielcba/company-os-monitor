import { apiFetch } from '@/api/client'
import type {
  AuditLogPage,
  AuditLogSort,
  CognitiveAnomaly,
  CognitiveAnomalyPage,
  CognitiveAnomalySort,
  CognitiveConfidenceDetail,
  CognitiveConfidencePage,
  CognitiveConfidenceSort,
  CognitiveConfidenceSummary,
  CognitiveConfidenceTargetType,
  CognitiveContext,
  CognitiveContextDetail,
  CognitiveContextPage,
  CognitiveContextSort,
  CognitiveDecisionDetail,
  CognitiveDecisionPage,
  CognitiveDecisionSort,
  CognitiveDecisionStatus,
  CognitiveHypothesisDetail,
  CognitiveHypothesisPage,
  CognitiveHypothesisSort,
  CognitiveHypothesisStatus,
  CognitiveInsightDetail,
  CognitiveInsightPage,
  CognitiveInsightSort,
  CognitiveLayer,
  CognitivePatternDetail,
  CognitivePatternPage,
  CognitivePatternSort,
  CognitiveRecommendationDetail,
  CognitiveRecommendationPage,
  CognitiveRecommendationSort,
  CognitiveRecommendationStatus,
  CognitiveReportDetail,
  CognitiveReportPage,
  CognitiveReportSort,
  CognitiveReportType,
  CognitiveSummary,
  AuditAction,
  AuditConcept,
  EvidenceDetail,
  EvidencePage,
  EvidenceSort,
  ObservationsPage,
  ObservationSort,
  QualityClass,
  ServicesHealthResponse,
  Tenant,
  TenantsPage,
} from '@/types/cognitive'

export async function fetchServicesHealth(): Promise<ServicesHealthResponse> {
  return apiFetch<ServicesHealthResponse>('/services/health')
}

export async function fetchCognitiveSummary(tenantId: string): Promise<CognitiveSummary> {
  return apiFetch<CognitiveSummary>(`/tenants/${tenantId}/cognitive/summary`)
}

export interface ObservationsQuery {
  limit?: number
  offset?: number
  fact_type?: string
  source_type?: string
  quality_class?: QualityClass | ''
  sort?: ObservationSort
}

export async function fetchObservations(
  tenantId: string,
  query: ObservationsQuery = {},
): Promise<ObservationsPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.fact_type) params.set('fact_type', query.fact_type)
  if (query.source_type) params.set('source_type', query.source_type)
  if (query.quality_class) params.set('quality_class', query.quality_class)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<ObservationsPage>(
    `/tenants/${tenantId}/observations${qs ? `?${qs}` : ''}`,
  )
}

export interface DecisionsQuery {
  limit?: number
  offset?: number
  status?: CognitiveDecisionStatus | ''
  sort?: CognitiveDecisionSort
}

export async function fetchDecisions(
  tenantId: string,
  query: DecisionsQuery = {},
): Promise<CognitiveDecisionPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.status) params.set('status', query.status)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveDecisionPage>(
    `/tenants/${tenantId}/decisions${qs ? `?${qs}` : ''}`,
  )
}

export async function fetchDecisionDetail(
  tenantId: string,
  decisionId: string,
): Promise<CognitiveDecisionDetail> {
  return apiFetch<CognitiveDecisionDetail>(
    `/tenants/${tenantId}/decisions/${decisionId}`,
  )
}

export interface EvidenceQuery {
  limit?: number
  offset?: number
  organization_type?: string
  quality_class?: QualityClass | ''
  sort?: EvidenceSort
}

export async function fetchEvidence(
  tenantId: string,
  query: EvidenceQuery = {},
): Promise<EvidencePage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.organization_type) params.set('organization_type', query.organization_type)
  if (query.quality_class) params.set('quality_class', query.quality_class)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<EvidencePage>(
    `/tenants/${tenantId}/evidence${qs ? `?${qs}` : ''}`,
  )
}

export async function fetchEvidenceDetail(
  tenantId: string,
  evidenceId: string,
): Promise<EvidenceDetail> {
  return apiFetch<EvidenceDetail>(`/tenants/${tenantId}/evidence/${evidenceId}`)
}

export interface ContextsQuery {
  limit?: number
  offset?: number
  purpose?: string
  mental_model_id?: string
  is_active?: string
  sort?: CognitiveContextSort
}

export async function fetchContexts(
  tenantId: string,
  query: ContextsQuery = {},
): Promise<CognitiveContextPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.purpose) params.set('purpose', query.purpose)
  if (query.mental_model_id) params.set('mental_model_id', query.mental_model_id)
  if (query.is_active) params.set('is_active', query.is_active)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveContextPage>(
    `/tenants/${tenantId}/contexts${qs ? `?${qs}` : ''}`,
  )
}

export async function fetchContextDetail(
  tenantId: string,
  contextId: string,
): Promise<CognitiveContextDetail> {
  return apiFetch<CognitiveContextDetail>(`/tenants/${tenantId}/contexts/${contextId}`)
}

export interface PatternsQuery {
  limit?: number
  offset?: number
  pattern_type?: string
  is_active?: string
  sort?: CognitivePatternSort
}

export async function fetchPatterns(
  tenantId: string,
  query: PatternsQuery = {},
): Promise<CognitivePatternPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.pattern_type) params.set('pattern_type', query.pattern_type)
  if (query.is_active) params.set('is_active', query.is_active)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitivePatternPage>(
    `/tenants/${tenantId}/patterns${qs ? `?${qs}` : ''}`,
  )
}

export async function fetchPatternDetail(
  tenantId: string,
  patternId: string,
): Promise<CognitivePatternDetail> {
  return apiFetch<CognitivePatternDetail>(`/tenants/${tenantId}/patterns/${patternId}`)
}

export interface ReportsQuery {
  limit?: number
  offset?: number
  report_type?: CognitiveReportType | ''
  sort?: CognitiveReportSort
}

export async function fetchReports(
  tenantId: string,
  query: ReportsQuery = {},
): Promise<CognitiveReportPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.report_type) params.set('report_type', query.report_type)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveReportPage>(
    `/tenants/${tenantId}/reports${qs ? `?${qs}` : ''}`,
  )
}

export async function fetchReportDetail(
  tenantId: string,
  reportId: string,
): Promise<CognitiveReportDetail> {
  return apiFetch<CognitiveReportDetail>(
    `/tenants/${tenantId}/reports/${reportId}`,
  )
}

export interface AnomaliesQuery {
  limit?: number
  offset?: number
  anomaly_class?: string
  sort?: CognitiveAnomalySort
}

export async function fetchAnomalies(
  tenantId: string,
  query: AnomaliesQuery = {},
): Promise<CognitiveAnomalyPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.anomaly_class) params.set('anomaly_class', query.anomaly_class)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveAnomalyPage>(
    `/tenants/${tenantId}/anomalies${qs ? `?${qs}` : ''}`
  )
}

export async function fetchAnomalyDetail(
  tenantId: string,
  anomalyId: string,
): Promise<{ anomaly: CognitiveAnomaly; context: CognitiveContext | null }> {
  return apiFetch<{ anomaly: CognitiveAnomaly; context: CognitiveContext | null }>(
    `/tenants/${tenantId}/anomalies/${anomalyId}`
  )
}

export interface HypothesesQuery {
  limit?: number
  offset?: number
  status?: CognitiveHypothesisStatus | ''
  sort?: CognitiveHypothesisSort
}

export async function fetchHypotheses(
  tenantId: string,
  query: HypothesesQuery = {},
): Promise<CognitiveHypothesisPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.status) params.set('status', query.status)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveHypothesisPage>(
    `/tenants/${tenantId}/hypotheses${qs ? `?${qs}` : ''}`
  )
}

export async function fetchHypothesisDetail(
  tenantId: string,
  hypothesisId: string,
): Promise<CognitiveHypothesisDetail> {
  return apiFetch<CognitiveHypothesisDetail>(
    `/tenants/${tenantId}/hypotheses/${hypothesisId}`
  )
}

export interface ConfidenceQuery {
  limit?: number
  offset?: number
  target_type?: CognitiveConfidenceTargetType | ''
  sort?: CognitiveConfidenceSort
}

export async function fetchConfidence(
  tenantId: string,
  query: ConfidenceQuery = {},
): Promise<CognitiveConfidencePage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.target_type) params.set('target_type', query.target_type)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveConfidencePage>(
    `/tenants/${tenantId}/confidence${qs ? `?${qs}` : ''}`
  )
}

export async function fetchConfidenceSummary(
  tenantId: string,
): Promise<CognitiveConfidenceSummary> {
  return apiFetch<CognitiveConfidenceSummary>(
    `/tenants/${tenantId}/confidence/summary`
  )
}

export async function fetchConfidenceDetail(
  tenantId: string,
  confidenceId: string,
): Promise<CognitiveConfidenceDetail> {
  return apiFetch<CognitiveConfidenceDetail>(
    `/tenants/${tenantId}/confidence/${confidenceId}`
  )
}

export interface RecommendationsQuery {
  limit?: number
  offset?: number
  status?: CognitiveRecommendationStatus | ''
  sort?: CognitiveRecommendationSort
}

export async function fetchRecommendations(
  tenantId: string,
  query: RecommendationsQuery = {},
): Promise<CognitiveRecommendationPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.status) params.set('status', query.status)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveRecommendationPage>(
    `/tenants/${tenantId}/recommendations${qs ? `?${qs}` : ''}`
  )
}

export async function fetchRecommendationDetail(
  tenantId: string,
  recommendationId: string,
): Promise<CognitiveRecommendationDetail> {
  return apiFetch<CognitiveRecommendationDetail>(
    `/tenants/${tenantId}/recommendations/${recommendationId}`
  )
}

// ── Audit Log ─────────────────────────────────────────────────────────────

export interface AuditLogsQuery {
  limit?: number
  offset?: number
  user_id?: string
  cognitive_layer?: CognitiveLayer | ''
  cognitive_concept?: AuditConcept | ''
  action?: AuditAction | ''
  date_from?: string
  date_to?: string
  sort?: AuditLogSort
}

export async function fetchAuditLogs(
  tenantId: string,
  query: AuditLogsQuery = {},
): Promise<AuditLogPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.user_id) params.set('user_id', query.user_id)
  if (query.cognitive_layer) params.set('cognitive_layer', query.cognitive_layer)
  if (query.cognitive_concept) params.set('cognitive_concept', query.cognitive_concept)
  if (query.action) params.set('action', query.action)
  if (query.date_from) params.set('date_from', query.date_from)
  if (query.date_to) params.set('date_to', query.date_to)
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<AuditLogPage>(
    `/tenants/${tenantId}/audit${qs ? `?${qs}` : ''}`
  )
}

// ── Insights (Reasoning - Restructure) ────────────────────────────────────

export interface InsightsQuery {
  limit?: number
  offset?: number
  sort?: CognitiveInsightSort
}

export async function fetchInsights(
  tenantId: string,
  query: InsightsQuery = {},
): Promise<CognitiveInsightPage> {
  const params = new URLSearchParams()
  if (query.limit != null) params.set('limit', String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  if (query.sort) params.set('sort', query.sort)
  const qs = params.toString()
  return apiFetch<CognitiveInsightPage>(
    `/tenants/${tenantId}/insights${qs ? `?${qs}` : ''}`
  )
}

export async function fetchInsightDetail(
  tenantId: string,
  insightId: string,
): Promise<CognitiveInsightDetail> {
  return apiFetch<CognitiveInsightDetail>(
    `/tenants/${tenantId}/insights/${insightId}`
  )
}

// ── Tenants (superadmin) ──────────────────────────────────────────────────

export async function fetchTenants(): Promise<TenantsPage> {
  return apiFetch<TenantsPage>('/user/tenants')
}

export async function fetchTenantDetail(tenantId: string): Promise<Tenant> {
  return apiFetch<Tenant>(`/user/tenants/${tenantId}`)
}

