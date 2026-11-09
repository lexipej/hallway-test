// Hallway Test — Desktop half. A page that follows runs live and shows finished reports.
// Plain ESM loaded uncompiled by Hermes Desktop: no JSX, only the three allowed imports.
import * as sdk from '@hermes/plugin-sdk'
import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, useQuery, atom, useValue, Button, Input, Textarea, SandboxedFrame } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'hallway-test'
const $selected = atom(null)
let rest = null

const PEOPLE = {
  first_timer: { name: 'Mara', who: 'first-time visitor', initials: 'M', hue: '#b4532a' },
  low_vision: { name: 'Lolo Ben', who: '72, low vision', initials: 'LB', hue: '#7c5a2e' },
  keyboard: { name: 'Jo', who: 'screen-reader user', initials: 'J', hue: '#2f5d62' },
  colourblind: { name: 'Rafael', who: 'red-green colour blind', initials: 'R', hue: '#6b4c8a' },
  shaky: { name: 'Aling Nena', who: 'hand tremor', initials: 'AN', hue: '#8a3b4f' }
}
const STATUS = {
  starting: 'Opening the page…', thinking: 'Looking at the screen…', acting: 'Doing it…',
  success: 'Finished', gave_up: 'Gave up', false_done: 'Thought they finished', out_of_steps: 'Still stuck', error: 'Run error'
}
const DONE = new Set(['success', 'gave_up', 'false_done', 'out_of_steps', 'error'])
const tone = s => (s === 'success' ? 'var(--ui-accent)' : DONE.has(s) ? 'var(--ui-text-primary, currentColor)' : 'var(--ui-text-tertiary)')

const muted = { color: 'var(--ui-text-tertiary)' }
const line = { border: '1px solid var(--ui-stroke-secondary)', borderRadius: 12 }

function ago(t) {
  if (!t) return ''
  const s = Math.max(1, Math.round(Date.now() / 1000 - t))
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : s < 86400 ? `${Math.round(s / 3600)}h ago` : `${Math.round(s / 86400)}d ago`
}

function scoreText(r) {
  if (!r.score) return r.status === 'running' || r.status === 'writing report' ? 'running…' : r.status || ''
  return (r.variants || ['before']).map(v => `${r.score[v].passed}/${r.score[v].total}`).join(' → ')
}

function send(text) {
  const ok = host.composer.submit(null, text)
  if (ok === false) host.notify({ kind: 'warning', message: 'Open a chat first, then press Run again.' })
  else host.notify({ kind: 'info', message: 'Sent to your chat. The run appears here in a few seconds.' })
}

function NewTest() {
  const [url, setUrl] = useState('')
  const [task, setTask] = useState('')
  const [success, setSuccess] = useState('')
  const [compare, setCompare] = useState('')
  const run = () => {
    if (!url.trim() || !task.trim()) return host.notify({ kind: 'warning', message: 'Add a page URL and a task.' })
    let p = `Run a hallway test with the hallway_test tool. url: ${url.trim()}. task: ${task.trim()}.`
    if (success.trim()) p += ` success_text: ${success.trim()}.`
    if (compare.trim()) p += ` compare_url: ${compare.trim()}.`
    send(p + ' Then show me the summary card and the top findings.')
  }
  const field = (label, el) => jsxs('label', { style: { display: 'grid', gap: 4, fontSize: 12, minWidth: 0 }, children: [jsx('span', { style: muted, children: label }), el] })
  return jsxs('div', {
    style: { ...line, padding: 12, display: 'grid', gap: 8 },
    children: [
      jsx('div', { style: { fontWeight: 600, fontSize: 13 }, children: 'New test' }),
      field('Page', jsx(Input, { value: url, style: { width: '100%', boxSizing: 'border-box' }, placeholder: 'http://localhost:3000/signup', onChange: e => setUrl(e.target.value) })),
      field('What should people try to do?', jsx(Textarea, { value: task, style: { width: '100%', boxSizing: 'border-box' }, rows: 2, placeholder: 'Sign up with sam@example.com', onChange: e => setTask(e.target.value) })),
      field('Text shown only on success (recommended)', jsx(Input, { value: success, style: { width: '100%', boxSizing: 'border-box' }, placeholder: 'Welcome aboard', onChange: e => setSuccess(e.target.value) })),
      field('Compare with (optional)', jsx(Input, { value: compare, style: { width: '100%', boxSizing: 'border-box' }, placeholder: 'http://localhost:3001/signup', onChange: e => setCompare(e.target.value) })),
      jsxs('div', {
        style: { display: 'flex', gap: 8 },
        children: [
          jsx(Button, { size: 'sm', onClick: run, children: 'Run test' }),
          jsx(Button, {
            size: 'sm', variant: 'outline',
            onClick: () => send('Run the hallway_test tool on the bundled demo: url "demo", compare_url "demo:fixed". Then show me the summary card and the top findings.'),
            children: 'Try the demo'
          })
        ]
      })
    ]
  })
}

function RunList({ runs, current }) {
  if (!runs.length) return jsx('div', { style: { ...muted, fontSize: 12, padding: '8px 2px' }, children: 'No runs yet. Try the demo.' })
  return jsx('div', {
    style: { display: 'grid', gap: 4 },
    children: runs.map(r => jsxs('button', {
      type: 'button', onClick: () => $selected.set(r.id),
      style: {
        textAlign: 'left', padding: '8px 10px', borderRadius: 10, cursor: 'pointer', background: 'transparent', color: 'inherit',
        border: r.id === current ? '1px solid var(--ui-accent)' : '1px solid transparent'
      },
      children: [
        jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 13 }, children: [
          jsx('span', { style: { fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: r.title || r.url }),
          jsx('span', { style: { fontVariantNumeric: 'tabular-nums' }, children: scoreText(r) })
        ] }),
        jsx('div', { style: { ...muted, fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: `${ago(r.created)} · ${r.task || ''}` })
      ]
    }, r.id))
  })
}

function Avatar({ id }) {
  const p = PEOPLE[id] || { initials: '?', hue: '#7c5a2e' }
  return jsx('div', {
    style: { width: 34, height: 34, borderRadius: 99, background: p.hue, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 12, flex: 'none' },
    children: p.initials
  })
}

function LiveView({ run }) {
  const order = run.personas_order || Object.keys(PEOPLE)
  const people = [...(run.people || [])].sort((a, b) => order.indexOf(a.persona) - order.indexOf(b.persona))
  const variants = run.variants || ['before']
  return jsxs('div', {
    style: { display: 'grid', gap: 14 },
    children: [
      jsxs('div', { children: [
        jsx('div', { style: { fontSize: 18, fontWeight: 600 }, children: run.title || run.url }),
        jsx('div', { style: { ...muted, fontSize: 13, fontStyle: 'italic' }, children: `“${run.task}”` }),
        jsx('div', { style: { ...muted, fontSize: 12, marginTop: 4 }, children: run.status === 'writing report' ? 'Writing the report…' : 'Each person is trying it now in their own browser.' })
      ] }),
      ...variants.map(v => jsxs('div', { children: [
        variants.length > 1 && jsx('div', { style: { ...muted, fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase', margin: '4px 0 8px' }, children: v === 'before' ? 'Before' : 'After changes' }),
        jsx('div', {
          style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10 },
          children: people.filter(p => p.variant === v).map(p => jsxs('div', {
            style: { ...line, padding: 10, display: 'grid', gap: 8, alignContent: 'start' },
            children: [
              jsxs('div', { style: { display: 'flex', gap: 8, alignItems: 'center' }, children: [
                jsx(Avatar, { id: p.persona }),
                jsxs('div', { style: { minWidth: 0 }, children: [
                  jsx('div', { style: { fontWeight: 600, fontSize: 13 }, children: (PEOPLE[p.persona] || {}).name || p.persona }),
                  jsx('div', { style: { fontSize: 11.5, color: tone(p.status) }, children: `${STATUS[p.status] || p.status}${p.step ? ` · step ${p.step}` : ''}` })
                ] })
              ] }),
              p.thumb && jsx('img', { src: p.thumb, alt: `What ${(PEOPLE[p.persona] || {}).name || 'this person'} sees`, style: { width: '100%', borderRadius: 8, border: '1px solid var(--ui-stroke-secondary)' } }),
              (p.quote || p.thought) && jsx('div', { style: { fontSize: 12.5, fontStyle: 'italic', fontFamily: 'Georgia, serif' }, children: `“${p.quote || p.thought}”` }),
              p.action && !DONE.has(p.status) && jsx('code', { style: { ...muted, fontSize: 11 }, children: p.action })
            ]
          }, p.key))
        })
      ] }, v))
    ]
  })
}

function ReportView({ id }) {
  const q = useQuery({ queryKey: [ID, 'report', id], queryFn: () => rest(`/runs/${id}/report`), staleTime: Infinity })
  if (q.isError) return jsx('div', { style: muted, children: 'Could not load the report.' })
  if (!q.data) return jsx('div', { style: muted, children: 'Loading report…' })
  return jsx(SandboxedFrame, { src: q.data.src, title: 'Hallway Test report', style: { width: '100%', height: '100%', minHeight: 600, borderRadius: 12 } })
}

function RunView({ id }) {
  const q = useQuery({
    queryKey: [ID, 'run', id], queryFn: () => rest(`/runs/${id}`),
    refetchInterval: query => (query.state.data && (query.state.data.status === 'done' || query.state.data.status === 'error') ? false : 1500)
  })
  const run = q.data
  if (!run) return jsx('div', { style: muted, children: q.isError ? 'This run is no longer available.' : 'Loading…' })
  if (run.status === 'done') return jsx(ReportView, { id })
  if (run.status === 'error') return jsx('div', { style: muted, children: `The run stopped: ${run.error || 'unknown error'}` })
  return jsx(LiveView, { run })
}

function HallwayPage() {
  const selected = useValue($selected)
  const q = useQuery({ queryKey: [ID, 'runs'], queryFn: () => rest('/runs'), refetchInterval: 4000 })
  const runs = (q.data && q.data.runs) || []
  const current = selected || (runs[0] && runs[0].id) || null
  return jsxs('div', {
    style: { display: 'grid', gridTemplateColumns: '300px 1fr', height: '100%', minHeight: 0 },
    children: [
      jsxs('div', {
        style: { borderRight: '1px solid var(--ui-stroke-secondary)', padding: 14, display: 'grid', gap: 14, alignContent: 'start', overflowY: 'auto' },
        children: [
          jsxs('div', { children: [
            jsx('div', { style: { fontSize: 16, fontWeight: 600 }, children: 'Hallway Test' }),
            jsx('div', { style: { ...muted, fontSize: 12 }, children: 'Five simulated people with real limits try your page.' })
          ] }),
          jsx(NewTest, {}),
          jsx('div', { style: { ...muted, fontSize: 11, letterSpacing: '.1em', textTransform: 'uppercase' }, children: 'Runs' }),
          q.isError ? jsx('div', { style: { ...muted, fontSize: 12 }, children: 'Backend not reachable. Enable hallway-test in plugins and restart the gateway.' })
            : jsx(RunList, { runs, current })
        ]
      }),
      jsx('div', {
        style: { padding: 16, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column' },
        children: current ? jsx(RunView, { id: current }, current)
          : jsx('div', { style: { ...muted, margin: 'auto', textAlign: 'center', maxWidth: 360 }, children: 'Run a test from the left, or ask Hermes: “hallway test my signup page”.' })
      })
    ]
  })
}

function CardRenderer({ file, result, fallback }) {
  const [src, setSrc] = useState(null)
  const runId = (String((result && result.run_id) || file.path || '').match(/\d{8}-\d{6}-[0-9a-f]{4}/) || [])[0]
  useEffect(() => {
    let live = true
    file.resolveUrl().then(u => live && setSrc(u), () => live && setSrc(''))
    return () => { live = false }
  }, [file])
  if (file.kind !== 'image' || !runId) return fallback
  return jsxs('figure', {
    style: { margin: 0, display: 'grid', gap: 6, maxWidth: 640 },
    children: [
      src ? jsx('img', { src, alt: 'Hallway Test summary card', style: { width: '100%', borderRadius: 12, border: '1px solid var(--ui-stroke-secondary)' } }) : fallback,
      jsx('div', { children: jsx(Button, { size: 'sm', variant: 'outline', onClick: () => { $selected.set(runId); host.navigate('/hallway') }, children: 'Open full report with replays' }) })
    ]
  })
}

export default {
  id: ID,
  name: 'Hallway Test',
  register(ctx) {
    rest = ctx.rest
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/hallway' }, render: () => jsx(HallwayPage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, order: 60, data: { path: '/hallway', label: 'Hallway Test', codicon: 'person' } },
      {
        id: 'open', area: PALETTE_AREA,
        data: { id: 'hallway-test.open', label: 'Hallway Test: open reports', keywords: ['usability', 'accessibility', 'persona', 'hallway'], run: () => host.navigate('/hallway') }
      }
    ])
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA === 'string') {
      ctx.register({ id: 'card', area: sdk.TOOL_MEDIA_RENDERER_AREA, data: { tools: ['hallway_test'], render: props => jsx(CardRenderer, props) } })
    }
  }
}
