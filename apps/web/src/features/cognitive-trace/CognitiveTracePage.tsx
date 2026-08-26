import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import { useCognitiveTrace } from '@/features/cognitive-trace/useCognitiveTrace'
import { TraceGraph, TraceWarnings } from '@/features/cognitive-trace/TraceGraph'
import { ApiError } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'

export function CognitiveTracePage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useCognitiveTrace(tenantId, reportId)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Cognitive Trace</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Provenance view (read model, external capability ADR-0002): it reconstructs,
            from the canonical cognitive stores, the chain of artifacts that justify a
            Report — it never fabricates nodes. Root is always a Report; broken
            provenance is reported explicitly as <span className="font-mono">partial</span>.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate('/action/reports')}>
          Back to reports
        </Button>
      </div>

      {!reportId ? (
        <EmptyState title="No report selected" description="Open a report and choose “View cognitive trace”." />
      ) : isPending ? (
        <LoadingState label="Loading cognitive trace…" />
      ) : isError ? (
        error instanceof ApiError && error.status === 404 ? (
          <EmptyState
            title="Report not found in this tenant"
            description="The Report does not exist or does not belong to your tenant. Provenance can never leak across tenants."
          />
        ) : error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view this cognitive trace" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-muted/30 p-3">
            <Badge variant="outline" className="font-mono text-xs">
              report {reportId}
            </Badge>
            <Badge variant="outline" className="font-mono text-xs">
              tenant {data.root.tenant_id}
            </Badge>
            {data.completeness === 'complete' ? (
              <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
                complete
              </Badge>
            ) : (
              <Badge className="border-amber-500/40 bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                partial
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {data.nodes.length} nodes · {data.edges.length} edges
            </span>
          </div>

          <TraceWarnings warnings={data.warnings} />
          <TraceGraph nodes={data.nodes} edges={data.edges} />
        </div>
      )}
    </div>
  )
}

export default CognitiveTracePage
