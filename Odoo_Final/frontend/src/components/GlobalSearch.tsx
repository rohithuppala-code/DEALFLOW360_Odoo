import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { api, type ApiOk } from '../api/client'
import { inr } from '../utils/format'
import { searchHits, type SearchPayload } from '../utils/search'

function highlight(text: string, q: string): ReactNode {
  if (!q) return text
  const i = text.toLowerCase().indexOf(q.toLowerCase())
  if (i < 0) return text
  return (
    <>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  )
}

export default function GlobalSearch() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [activeFor, setActiveFor] = useState('')
  const wrapRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 280)
    return () => window.clearTimeout(t)
  }, [q])

  const res = useQuery({
    queryKey: ['search', debounced],
    enabled: open && debounced.length >= 2,
    queryFn: async ({ signal }) =>
      (await api.get<ApiOk<SearchPayload>>('/search', { params: { q: debounced }, signal })).data.data,
    placeholderData: (prev) => prev,
  })

  const hits = useMemo(() => searchHits(res.data), [res.data])
  if (activeFor !== debounced) {
    setActiveFor(debounced)
    setActive(0)
  }

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  function go(href: string | null) {
    setOpen(false)
    if (href) nav(href)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      if (q) setQ('')
      else {
        setOpen(false)
        inputRef.current?.blur()
      }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!hits.length) return
      setActive((i) => (i + 1) % hits.length)
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (!hits.length) return
      setActive((i) => (i - 1 + hits.length) % hits.length)
    }
  }

  function submit() {
    const term = q.trim()
    const hit = hits[active]
    if (hit?.href) {
      go(hit.href)
      return
    }
    if (term) {
      setOpen(false)
      nav(`/search?q=${encodeURIComponent(term)}`)
    }
  }

  const showPanel = open && (q.trim().length > 0 || debounced.length >= 2)
  let lastGroup = ''

  return (
    <div className="search-wrap" ref={wrapRef}>
      <form
        className="search-box"
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <Search size={14} aria-hidden />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search quotes, customers, products…"
          aria-label="Search quotes, customers, products"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls="global-search-results"
          aria-autocomplete="list"
          aria-activedescendant={showPanel && hits[active] ? `search-hit-${active}` : undefined}
        />
      </form>
      {showPanel ? (
        <div className="search-panel" id="global-search-results" role="listbox">
          {q.trim().length < 2 ? (
            <div className="search-msg">Type at least two characters</div>
          ) : res.isError && hits.length === 0 ? (
            <div className="search-msg">We couldn’t search. Try again.</div>
          ) : hits.length === 0 && res.isFetching ? (
            <div className="search-msg">Searching…</div>
          ) : hits.length === 0 ? (
            <div className="search-msg">No matches for “{debounced}”</div>
          ) : (
            hits.map((hit, i) => {
              const head = hit.groupLabel !== lastGroup
              lastGroup = hit.groupLabel
              return (
                <div key={hit.key}>
                  {head ? <div className="search-group">{hit.groupLabel}</div> : null}
                  <button
                    type="button"
                    id={`search-hit-${i}`}
                    role="option"
                    aria-selected={i === active}
                    className={`search-hit ${i === active ? 'active' : ''}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(hit.href)}
                  >
                    <span>
                      <strong>{highlight(hit.title, debounced)}</strong>
                      {hit.meta ? <span className="muted"> {highlight(hit.meta, debounced)}</span> : null}
                    </span>
                    {hit.amount != null ? <span className="mono muted">{inr(hit.amount, true)}</span> : null}
                  </button>
                </div>
              )
            })
          )}
        </div>
      ) : null}
    </div>
  )
}
