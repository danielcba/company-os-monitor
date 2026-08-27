import { useQuery } from '@tanstack/react-query'
import { fetchCognitiveTimeline } from '@/api/gateway'
import type { CognitiveTimelineResponse } from '@/types/cognitive'

export function useCognitiveTimeline(
  tenantId: string | undefined,
  params: { limit?: number; ascending?: boolean } = {},
) {
  return useQuery({
    queryKey: ['cognitive-timeline', tenantId, params],
    queryFn: () => fetchCognitiveTimeline(tenantId!, params),
    enabled: Boolean(tenantId),
  })
}

export type { CognitiveTimelineResponse }
