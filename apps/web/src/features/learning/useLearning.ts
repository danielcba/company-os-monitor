import { useQuery } from '@tanstack/react-query'
import {
  fetchContextRevision,
  fetchInsightTransformations,
  fetchPatternRefinement,
} from '@/api/gateway'
import type {
  ContextRevisionResponse,
  InsightTransformationResponse,
  PatternRefinementResponse,
} from '@/types/cognitive'

export function usePatternRefinement(tenantId: string | undefined) {
  return useQuery({
    queryKey: ['pattern-refinement', tenantId],
    queryFn: () => fetchPatternRefinement(tenantId!),
    enabled: Boolean(tenantId),
  })
}

export function useContextRevision(tenantId: string | undefined) {
  return useQuery({
    queryKey: ['context-revision', tenantId],
    queryFn: () => fetchContextRevision(tenantId!),
    enabled: Boolean(tenantId),
  })
}

export function useInsightTransformations(tenantId: string | undefined) {
  return useQuery({
    queryKey: ['insight-transformations', tenantId],
    queryFn: () => fetchInsightTransformations(tenantId!),
    enabled: Boolean(tenantId),
  })
}

export type { PatternRefinementResponse, ContextRevisionResponse, InsightTransformationResponse }
