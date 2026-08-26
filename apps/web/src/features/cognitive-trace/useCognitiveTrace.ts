import { useQuery } from '@tanstack/react-query'
import { fetchCognitiveTrace } from '@/api/gateway'
import type { CognitiveTraceResponse } from '@/types/cognitive'

export function useCognitiveTrace(
  tenantId: string | undefined,
  reportId: string | undefined,
) {
  return useQuery({
    queryKey: ['cognitive-trace', tenantId, reportId],
    queryFn: () => fetchCognitiveTrace(tenantId!, reportId!),
    enabled: Boolean(tenantId && reportId),
  })
}

export type { CognitiveTraceResponse }
