import { expect, test } from 'claude-code/testing'

// What Claude Code passes to the ui.render hook for the panel, outside a surface
const PANE = {
  plugin: 'compteur-escale',
  component: 'Pane',
  requestId: 'compteur',
  viewport: { columns: 100, rows: 30 },
  props: {
    title: 'Compteur Escale',
    isFocused: true,
    bodyColumns: 60,
    placement: 'inline',
    scroll: { offset: 0, bodyRows: 12 },
    view: {},
  },
} as const

const COMMAND = {
  command: 'cout',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: false, columns: 100 },
} as const

const USAGE = {
  input_tokens: 1200,
  output_tokens: 300,
  cache_read_input_tokens: 8000,
  cache_creation_input_tokens: 800,
  model: 'claude-test',
}

const BOOKING = { tool: 'mcp__escale__book_hotel', hotel: 'Le Confluent', city: 'Lyon', nights: 2 }

test('a finished turn is counted, summed up by /cout and drawn in the panel', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('tool.call', () => ({ result: 'ok' }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))

  await $.turn.start({ turnId: 't1', text: "Quel est le plafond d'hôtel à Lyon ?" })
  await $.tool.call({ tool: 'mcp__escale__search_travel_policy', query: 'plafond hôtel' })
  await $.tool.call({ tool: 'Bash', command: 'uv run pytest -q' })
  await $.turn.complete({ turnId: 't1', answer: 'ok', durationMs: 12000, isAborted: false, reason: 'answer', usage: USAGE })

  const reply = await $.command.run(COMMAND)
  expect(reply.text).toContain('1 tour(s) dont 0 de sous-agent(s) : 1200 tokens en entrée, 300 en sortie')
  // 8000 read out of 1200 + 8000 + 800 = 10000 input tokens: 80 %
  expect(reply.text).toContain('8000 lus depuis le cache (80 %')
  expect(reply.text).toContain('2 appel(s)')

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ key: 'totals' }))?.text).toContain('10000 en entrée, 300 en sortie, cache 80 %')
    expect((await ui.find({ key: 'turn-0' }))?.text).toContain('#1')
    await ui.unmount()
  }
})

test('a subagent turn is shown apart and does not count the main tool calls', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('tool.call', () => ({ result: 'ok' }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))

  await $.turn.start({ turnId: 't1', text: 'Prépare mon voyage' })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await $.turn.complete({ turnId: 't1', agentId: 'sub1', answer: 'ok', durationMs: 3000, isAborted: false, reason: 'answer', usage: USAGE })

  const reply = await $.command.run(COMMAND)
  expect(reply.text).toContain('1 tour(s) dont 1 de sous-agent(s)')
  expect(reply.text).toContain('0 appel(s)')

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ key: 'turn-0' }))?.text).toContain('a1')
  await ui.unmount()
})

test('book_hotel goes through when the user confirms', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion'
      ? { result: { answers: { [e.questions[0]?.question ?? '']: 'Réserver' } } }
      : { result: 'réservé' },
  )
  const ran = await $.tool.call(BOOKING)
  expect(ran.result).toBe('réservé')
})

test('book_hotel is refused when the user refuses, and the refusal is counted', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion'
      ? { result: { answers: { [e.questions[0]?.question ?? '']: 'Refuser' } } }
      : { result: 'réservé' },
  )
  on('ui.open', () => ({ value: { isPlaced: true } }))
  const ran = await $.tool.call({ ...BOOKING, hotel: 'Grand Palais Bellecour', nights: 5 })
  expect(ran.deny).toContain('refusé')
  expect(ran.result).toBeUndefined()
  const reply = await $.command.run(COMMAND)
  expect(reply.text).toContain('Aucun tour terminé dans cette session, 1 réservation(s) refusée(s)')
})

test('book_hotel is refused when nobody can answer (claude -p): the guard fails closed', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion' ? { deny: 'personne pour répondre' } : { result: 'réservé' },
  )
  const ran = await $.tool.call(BOOKING)
  expect(ran.deny).toBeDefined()
  expect(ran.result).toBeUndefined()
})

test('another Escale tool is not held back', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion' ? { result: { answers: {} } } : { result: '2 passages' },
  )
  const ran = await $.tool.call({ tool: 'mcp__escale__search_travel_policy', query: 'plafond' })
  expect(ran.result).toBe('2 passages')
})
