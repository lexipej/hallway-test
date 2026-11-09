// Hallway Test — Desktop half. A page that follows runs live and shows finished reports.
// Plain ESM loaded uncompiled by Hermes Desktop: no JSX, only the three allowed imports.
import * as sdk from '@hermes/plugin-sdk'
import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, useQuery, atom, useValue, Button, Input, Textarea, SandboxedFrame } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'hallway-test'
const $selected = atom(null)
let rest = null
let os = null

// Condition and status icons (same set as the report; generated from ht/icons.py).
const ICONS = {"new": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1z\"/>", "low_vision": "<circle cx=\"7\" cy=\"14.5\" r=\"3.6\"/><circle cx=\"17\" cy=\"14.5\" r=\"3.6\"/><path d=\"M10.6 14.2c.9-.6 1.9-.6 2.8 0M3.4 14 5.2 7.5M20.6 14 18.8 7.5\"/>", "screen_reader": "<path d=\"M4 15.5V12a8 8 0 0 1 16 0v3.5\"/><rect x=\"3\" y=\"14\" width=\"4.2\" height=\"6.5\" rx=\"1.6\"/><rect x=\"16.8\" y=\"14\" width=\"4.2\" height=\"6.5\" rx=\"1.6\"/>", "keyboard": "<rect x=\"2.5\" y=\"6\" width=\"19\" height=\"12\" rx=\"2\"/><path d=\"M6.5 10h.01M10.5 10h.01M14.5 10h.01M18 10h.01M7.5 14h9\"/>", "colour": "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M12 3a9 9 0 0 0 0 18z\" fill=\"currentColor\" stroke=\"none\"/>", "tremor": "<circle cx=\"11\" cy=\"13\" r=\"7.5\"/><circle cx=\"11\" cy=\"13\" r=\"2.6\"/><circle cx=\"18.2\" cy=\"5.8\" r=\"1.7\" fill=\"currentColor\" stroke=\"none\"/><path d=\"M15.6 3.6l.9-.9M20.4 8.4l.9-.9\"/>", "check": "<path d=\"M5 12.5l4.2 4.2L19 7\"/>", "cross": "<path d=\"M6.5 6.5l11 11M17.5 6.5l-11 11\"/>", "alert": "<path d=\"M12 4 2.8 19.5h18.4z\"/><path d=\"M12 10v4.2M12 17h.01\"/>", "tap": "<circle cx=\"12\" cy=\"12\" r=\"3\"/><path d=\"M12 3v3M12 18v3M3 12h3M18 12h3\"/>"}
const Icon = ({ name, size = 14 }) => jsx('span', {
  'aria-hidden': true, style: { display: 'inline-flex', width: size, height: size, flex: 'none' },
  dangerouslySetInnerHTML: { __html: `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ICONS.new}</svg>` }
})
const FALLBACK_PEOPLE = {
  first_timer: { first: 'Maya', initials: 'M', icon: 'new', condition: 'First visit' },
  low_vision: { first: 'Walter', initials: 'W', icon: 'low_vision', condition: 'Low vision' },
  keyboard: { first: 'Jordan', initials: 'J', icon: 'screen_reader', condition: 'Screen reader' },
  colourblind: { first: 'Ryan', initials: 'R', icon: 'colour', condition: 'Colour blind' },
  shaky: { first: 'Nina', initials: 'N', icon: 'tremor', condition: 'Hand tremor' }
}
const personOf = (run, id) => ((run && run.people) || []).find(p => p.id === id) || FALLBACK_PEOPLE[id] || { first: id, initials: '?', icon: 'new', condition: '' }
const STATUS = {
  starting: 'Opening', thinking: 'Looking', acting: 'Acting',
  success: 'Finished', gave_up: 'Gave up', false_done: 'False finish', out_of_steps: 'Stuck', error: 'Run error'
}
const STAMP = { success: ['check', 'var(--ui-green)'], gave_up: ['cross', 'var(--ui-red)'], out_of_steps: ['cross', 'var(--ui-red)'],
  false_done: ['alert', 'var(--ui-yellow)'], error: ['alert', 'var(--ui-text-tertiary)'] }
const mono = { fontFamily: 'ui-monospace, "Cascadia Mono", "JetBrains Mono", Consolas, monospace' }
const caps = { ...mono, fontSize: 10.5, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase' }
const DONE = new Set(['success', 'gave_up', 'false_done', 'out_of_steps', 'error'])

const muted = { color: 'var(--ui-text-tertiary)' }
const line = { border: '1px solid var(--ui-stroke-secondary)', borderRadius: 2 }

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
    style: { ...line, padding: 12, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 8, minWidth: 0 },
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
    style: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 4, minWidth: 0 },
    children: runs.map(r => jsxs('button', {
      type: 'button', onClick: () => $selected.set(r.id),
      style: {
        width: '100%', minWidth: 0, textAlign: 'left', padding: '8px 10px', borderRadius: 10, cursor: 'pointer', background: 'transparent', color: 'inherit',
        border: r.id === current ? '1px solid var(--ui-accent)' : '1px solid transparent'
      },
      children: [
        jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 13 }, children: [
          jsx('span', { style: { fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: r.title || r.url }),
          jsx('span', { style: { fontVariantNumeric: 'tabular-nums', flex: 'none' }, children: scoreText(r) })
        ] }),
        jsx('div', { style: { ...muted, fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: `${ago(r.created)} · ${r.task || ''}` })
      ]
    }, r.id))
  })
}

function useAvatars() {
  const q = useQuery({ queryKey: [ID, 'avatars'], queryFn: () => rest('/avatars'), staleTime: Infinity })
  return q.data || {}
}

function Avatar({ id, person, size = 40 }) {
  const avatars = useAvatars()
  const src = avatars[id]
  return jsx('div', {
    style: { width: size, height: size, flex: 'none', overflow: 'hidden', borderRadius: '50%', background: 'var(--ui-accent)', color: 'var(--ui-base, #fff)',
             display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: size * 0.38 },
    children: src ? jsx('img', { src, alt: '', style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' } }) : person.initials
  })
}

function Chip({ person }) {
  return jsxs('span', {
    style: { display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--ui-text-tertiary)', whiteSpace: 'nowrap' },
    children: [jsx(Icon, { name: person.icon, size: 12 }), person.condition]
  })
}

function Stamp({ status, step }) {
  const [ic, color] = STAMP[status] || ['tap', 'var(--ui-text-tertiary)']
  const live = !DONE.has(status)
  return jsxs('span', {
    style: { display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: live ? 'var(--ui-text-tertiary)' : color, whiteSpace: 'nowrap' },
    children: [live ? jsx('span', { style: { width: 6, height: 6, borderRadius: 6, background: 'var(--ui-accent)' } }) : jsx(Icon, { name: ic, size: 13 }),
               live && step ? `Step ${step}` : (STATUS[status] || status)]
  })
}

function LiveView({ run }) {
  const order = run.personas_order || Object.keys(FALLBACK_PEOPLE)
  const people = [...(run.people_live || [])].sort((a, b) => order.indexOf(a.persona) - order.indexOf(b.persona))
  const variants = run.variants || ['before']
  const finished = people.filter(p => DONE.has(p.status)).length
  return jsxs('div', {
    style: { display: 'grid', gap: 28, maxWidth: 1200 },
    children: [
      jsxs('div', { style: { display: 'grid', gap: 6 }, children: [
        jsx('div', { style: { fontSize: 12, color: 'var(--ui-text-tertiary)' },
          children: run.status === 'writing report' ? 'Writing the report…' : `Live · ${finished} of ${people.length} done` }),
        jsx('div', { style: { fontSize: 24, fontWeight: 750, letterSpacing: '-.02em', lineHeight: 1.15 }, children: run.title || run.url }),
        jsx('div', { style: { fontSize: 14, color: 'var(--ui-text-secondary, var(--ui-text-tertiary))', maxWidth: 760 }, children: run.task })
      ] }),
      ...variants.map(v => jsxs('div', { style: { display: 'grid', gap: 10 }, children: [
        variants.length > 1 && jsx('div', { style: { fontSize: 13, fontWeight: 600, color: 'var(--ui-text-tertiary)' }, children: v === 'before' ? 'Before' : 'After changes' }),
        jsx('div', {
          style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 14 },
          children: people.filter(p => p.variant === v).map(p => {
            const person = personOf(run, p.persona)
            return jsxs('div', {
              style: { background: 'var(--ui-bg-elevated)', borderRadius: 10, padding: 12, display: 'grid', gap: 10, alignContent: 'start' },
              children: [
                jsxs('div', { style: { display: 'flex', gap: 10, alignItems: 'center' }, children: [
                  jsx(Avatar, { id: p.persona, person, size: 34 }),
                  jsxs('div', { style: { display: 'grid', gap: 2, minWidth: 0, flex: 1 }, children: [
                    jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 6, alignItems: 'baseline' }, children: [
                      jsx('span', { style: { fontWeight: 650, fontSize: 14 }, children: person.first || person.name }),
                      jsx(Stamp, { status: p.status, step: p.step })
                    ] }),
                    jsx(Chip, { person })
                  ] })
                ] }),
                p.thumb ? jsx('img', { src: p.thumb, alt: `What ${person.first || 'this person'} sees`, style: { width: '100%', display: 'block', borderRadius: 6 } })
                  : jsx('div', { style: { aspectRatio: '420 / 860', borderRadius: 6, background: 'var(--ui-bg-tertiary, transparent)' } }),
                (p.quote || p.thought) && jsx('div', { style: { fontSize: 13, lineHeight: 1.4, color: 'var(--ui-text-secondary, inherit)' }, children: `“${p.quote || p.thought}”` })
              ]
            }, p.key)
          })
        })
      ] }, v))
    ]
  })
}

function ReportView({ id }) {
  const q = useQuery({ queryKey: [ID, 'report', id], queryFn: () => rest(`/runs/${id}/report`), staleTime: Infinity })
  const frame = useRef(null)
  if (q.isError) return jsx('div', { style: muted, children: 'Could not load the report.' })
  if (!q.data) return jsx('div', { style: muted, children: 'Loading report…' })
  // The page arrives without screenshots (data: URLs are capped at 2 MB); post them in once it has loaded.
  const post = () => {
    const w = frame.current && frame.current.contentWindow
    if (w && q.data.images) w.postMessage({ type: 'hallway-images', css: q.data.images }, '*')
  }
  const fileUrl = q.data.path ? 'file:///' + q.data.path.replace(/\\/g, '/').replace(/^\/+/, '') : ''
  const openIn = () => os && os.openExternal(fileUrl).then(ok => ok || host.notify({ kind: 'warning', message: 'Could not open the report. Use Show file instead.' }))
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minHeight: 0 },
    children: [
      os && q.data.path && jsxs('div', { style: { display: 'flex', gap: 8, justifyContent: 'flex-end' }, children: [
        jsx(Button, { size: 'sm', variant: 'outline', onClick: openIn, children: 'Open in browser' }),
        jsx(Button, { size: 'sm', variant: 'ghost', onClick: () => os.revealPath(q.data.path), children: 'Show file' })
      ] }),
      jsx(SandboxedFrame, {
        ref: frame, onLoad: post, src: q.data.src, title: 'Hallway Test report',
        style: { width: '100%', flex: 1, minHeight: 600, borderRadius: 12 }
      })
    ]
  })
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
        style: { borderRight: '1px solid var(--ui-stroke-secondary)', padding: 14, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 14, alignContent: 'start', overflowY: 'auto', overflowX: 'hidden', minWidth: 0 },
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
    os = ctx.os || null
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
