import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Eye, Shield } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchAuditLogs } from '@/api/gateway'
import type { AuditLogEntry, AuditLogSort, CognitiveLayer, AuditConcept, AuditAction } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { Badge } from '@/components/ui/badge'
import { AuditDetail } from '@/features/audit/AuditDetail'

const PAGE_SIZE = 50

const LAYER_COLORS: Record<string, string> = {
  perception: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  reasoning: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
  confidence: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300',
  action: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  memory: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
}

function LayerBadge({ layer }: { layer: string }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${LAYER_COLORS[layer] ?? ''}`}>
      {layer}
    </span>
  )
}

export function AuditPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [userId, setUserId] = useState('')
  const [cognitiveLayer, setCognitiveLayer] = useState<CognitiveLayer | ''>('')
  const [cognitiveConcept, setCognitiveConcept] = useState<AuditConcept | ''>('')
  const [actionFilter, setActionFilter] = useState<AuditAction | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sort, setSort] = useState<AuditLogSort>('timestamp_desc')
  const [selected, setSelected] = useState<AuditLogEntry | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['audit', tenantId, { offset, userId, cognitiveLayer, cognitiveConcept, actionFilter, dateFrom, dateTo, sort }],
    queryFn: () =>
      fetchAuditLogs(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        user_id: userId || undefined,
        cognitive_layer: cognitiveLayer || undefined,
        cognitive_concept: cognitiveConcept || undefined,
        action: actionFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(userId || cognitiveLayer || cognitiveConcept || actionFilter || dateFrom || dateTo)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5 text-muted-foreground" />
            Audit Log
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Episodic Memory — immutable record of what happened, when, and in order (append-only).
            Each entry traces a cognitive action through the pipeline.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Cognitive layer
            <select
              value={cognitiveLayer}
              onChange={(e) => {
                setCognitiveLayer(e.target.value as CognitiveLayer | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.cognitive_layers ?? []).map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Concept
            <select
              value={cognitiveConcept}
              onChange={(e) => {
                setCognitiveConcept(e.target.value as AuditConcept | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.cognitive_concepts ?? []).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Action
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value as AuditAction | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.actions ?? []).map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            User ID
            <Input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              onBlur={applyFilter}
              placeholder="UUID…"
              className="w-40"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            From
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value)
                applyFilter()
              }}
              className="w-36"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            To
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value)
                applyFilter()
              }}
              className="w-36"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as AuditLogSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="timestamp_desc">Newest first</option>
              <option value="timestamp_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading audit log…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view audit log" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.entries.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No audit entries match the filters' : 'No audit entries yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Audit entries appear here as the pipeline processes cognitive artifacts.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Timestamp</th>
                  <th className="px-3 py-2 font-medium">Layer</th>
                  <th className="px-3 py-2 font-medium">Concept</th>
                  <th className="px-3 py-2 font-medium">Action</th>
                  <th className="px-3 py-2 font-medium">User</th>
                  <th className="px-3 py-2 font-medium">Resource</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry) => (
                  <tr
                    key={entry.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(entry)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <LayerBadge layer={entry.cognitive_layer} />
                    </td>
                    <td className="px-3 py-2 font-medium">{entry.cognitive_concept}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline">{entry.action}</Badge>
                    </td>
                    <td className="max-w-[120px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                      {entry.user_id ? entry.user_id.slice(0, 8) : '—'}
                    </td>
                    <td className="max-w-[140px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                      {entry.resource_id.slice(0, 8)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Eye className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} entries · page {page} of {totalPages.toLocaleString()}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - data.limit))}
              >
                <ChevronLeft className="h-4 w-4" /> Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + data.limit >= data.total}
                onClick={() => setOffset(offset + data.limit)}
              >
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}

      <AuditDetail entry={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default AuditPage
