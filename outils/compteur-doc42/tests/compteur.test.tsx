import { expect, test } from 'claude-code/testing'

// Ce que Claude Code passe au hook ui.render pour le panneau, hors surface
const PANE = {
  plugin: 'compteur-doc42',
  component: 'Pane',
  requestId: 'compteur',
  viewport: { columns: 100, rows: 30 },
  props: {
    title: 'Compteur Doc42',
    isFocused: true,
    bodyColumns: 60,
    placement: 'inline',
    scroll: { offset: 0, bodyRows: 12 },
    view: {},
  },
} as const

const COMMANDE = {
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

test('un tour terminé est compté, résumé par /cout et dessiné dans le panneau', async ($, on) => {
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('tool.call', () => ({ result: 'ok' }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.open', () => ({ value: { isPlaced: true } }))

  await $.turn.start({ turnId: 't1', text: 'Quelles sont les échéances du contrat Alpha ?' })
  await $.tool.call({ tool: 'Read', file_path: 'corpus/alpha.md' })
  await $.tool.call({ tool: 'Bash', command: 'uv run pytest -q' })
  await $.turn.complete({ turnId: 't1', answer: 'ok', durationMs: 12000, isAborted: false, reason: 'answer', usage: USAGE })

  const reponse = await $.command.run(COMMANDE)
  expect(reponse.text).toContain('1 tour(s) : 1200 tokens en entrée, 300 en sortie')
  // 8000 lus sur 1200 + 8000 + 800 = 10000 en entrée : 80 %
  expect(reponse.text).toContain('8000 lus depuis le cache (80 %')
  expect(reponse.text).toContain('2 appel(s)')

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ key: 'totaux' }))?.text).toContain('10000 en entrée, 300 en sortie, cache 80 %')
    expect((await ui.find({ key: 'tour-0' }))?.text).toContain('#1')
    await ui.unmount()
  }
})

test('creer_fiche passe quand la personne confirme', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion'
      ? { result: { answers: { [e.questions[0]?.question ?? '']: 'Créer la fiche' } } }
      : { result: 'fiche créée' },
  )
  const ran = await $.tool.call({ tool: 'mcp__doc42__creer_fiche', titre: 'Synthèse Alpha' })
  expect(ran.result).toBe('fiche créée')
})

test('creer_fiche est refusée quand la personne refuse, et le refus est compté', async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion'
      ? { result: { answers: { [e.questions[0]?.question ?? '']: 'Refuser' } } }
      : { result: 'fiche créée' },
  )
  on('ui.open', () => ({ value: { isPlaced: true } }))
  const ran = await $.tool.call({ tool: 'mcp__doc42__creer_fiche', titre: 'COMPROMIS' })
  expect(ran.deny).toContain('refusé')
  expect(ran.result).toBeUndefined()
  const reponse = await $.command.run(COMMANDE)
  expect(reponse.text).toContain('Aucun tour terminé dans cette session, 1 fiche(s) refusée(s)')
})

test("creer_fiche est refusée quand personne ne peut répondre (claude -p)", async ($, on) => {
  on('tool.call', ($, e) =>
    e.tool === 'AskUserQuestion' ? { deny: 'personne pour répondre' } : { result: 'fiche créée' },
  )
  const ran = await $.tool.call({ tool: 'mcp__doc42__creer_fiche', titre: 'Synthèse Beta' })
  expect(ran.deny).toBeDefined()
  expect(ran.result).toBeUndefined()
})

test("un autre outil MCP de Doc42 n'est pas retenu", async ($, on) => {
  on('tool.call', ($, e) => (e.tool === 'AskUserQuestion' ? { result: { answers: {} } } : { result: '3 documents' }))
  const ran = await $.tool.call({ tool: 'mcp__doc42__chercher_documents', requete: 'échéances' })
  expect(ran.result).toBe('3 documents')
})
