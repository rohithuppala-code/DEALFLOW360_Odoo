import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type ApiOk } from '../api/client'
import { Btn, Empty, ErrorState, PageHeader } from '../components/ui'
import { when } from '../utils/format'

type Note = {
  id: number
  title: string
  message: string
  is_read: boolean
  related_entity_type?: string
  related_entity_id?: number
  created_at?: string
}

export default function NotificationsPage() {
  const qc = useQueryClient()
  const nav = useNavigate()
  const q = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => (await api.get<ApiOk<Note[]>>('/notifications')).data.data,
  })
  const read = useMutation({
    mutationFn: async (id: number) => api.post(`/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const readAll = useMutation({
    mutationFn: async () => api.post('/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const rows = q.data || []
  const unread = rows.filter((n) => !n.is_read).length

  function openNote(n: Note) {
    if (n.related_entity_type !== 'quote' || !n.related_entity_id) return
    const isNego = String(n.title || '').toLowerCase().includes('negotiat') || String(n.message || '').toLowerCase().includes('negotiat')
    nav(isNego ? `/quotes/${n.related_entity_id}?tab=Negotiate` : `/quotes/${n.related_entity_id}`)
  }

  if (q.isError) return <ErrorState title="We couldn't load notifications." onRetry={() => q.refetch()} />

  return (
    <div className="stack">
      <PageHeader
        kicker="Inbox"
        title="Notifications"
        subtitle="Approvals, negotiations, and inventory alerts."
        actions={
          unread > 0 ? (
            <Btn kind="ghost" disabled={readAll.isPending} onClick={() => readAll.mutate()}>
              {readAll.isPending ? 'Updating…' : 'Mark all read'}
            </Btn>
          ) : undefined
        }
      />
      <div className="card">
        {rows.length === 0 && !q.isLoading ? (
          <Empty title="Inbox zero" body="No notifications right now." />
        ) : (
          rows.map((n) => (
            <div
              className={`note-row ${n.is_read ? '' : 'unread'}`}
              key={n.id}
              role={n.related_entity_type === 'quote' ? 'link' : undefined}
              tabIndex={n.related_entity_type === 'quote' ? 0 : undefined}
              onClick={() => openNote(n)}
              onKeyDown={(e) => { if (e.key === 'Enter') openNote(n) }}
            >
              <div>
                <strong>{n.title}</strong>
                <div className="muted">{n.message}</div>
                {n.created_at ? <time className="muted">{when(n.created_at)}</time> : null}
              </div>
              {!n.is_read ? (
                <button
                  className="btn sm ghost"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    read.mutate(n.id)
                  }}
                >
                  Mark read
                </button>
              ) : <span className="muted">Read</span>}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
