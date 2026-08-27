import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchContextRevision,
  fetchInsightTransformations,
  fetchLearningMemories,
  fetchPatternRefinement,
  persistLearningMemory,
} from '@/api/gateway'
import type {
  ContextRevisionResponse,
  InsightTransformationResponse,
  LearningMemoryResponse,
  LearningMemoryTargetType,
  PatternRefinementResponse,
  PersistLearningMemoryRequest,
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

export function useLearningMemories(tenantId: string | undefined) {
  return useQuery({
    queryKey: ['learning-memory', tenantId],
    queryFn: () => fetchLearningMemories(tenantId!),
    enabled: Boolean(tenantId),
  })
}

export function usePersistLearningMemory(tenantId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: PersistLearningMemoryRequest) =>
      persistLearningMemory(tenantId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learning-memory', tenantId] })
    },
  })
}

export type {
  PatternRefinementResponse,
  ContextRevisionResponse,
  InsightTransformationResponse,
  LearningMemoryResponse,
  LearningMemoryTargetType,
}
