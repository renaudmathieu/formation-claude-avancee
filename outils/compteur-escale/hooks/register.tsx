// Mod "compteur-escale": measure and guard what Claude Code does with Escale.
// - Counts the tokens of each turn (input, output, cache) and the tool calls.
// - /cout opens a panel with the latest turns and the totals of the session.
// - Holds every call to book_hotel of the Escale MCP server until the user confirms,
//   and refuses when the question cannot be asked (fails closed).
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Turn } from '../types'

const turns = atom({ plugin: 'compteur-escale', key: 'turns' } as const, [])
const refusedBookings = atom({ plugin: 'compteur-escale', key: 'refusedBookings' } as const, 0)

const PANE = 'compteur'
// The irreversible tool of section 6, as Claude Code names it: mcp__<server>__<tool>
const BOOK_HOTEL = 'mcp__escale__book_hotel'
const YES = 'Réserver'
const NO = 'Refuser'

// Tool calls of the main turn in progress (one variable is enough: one turn at a time)
let toolsOfTurn = 0

function totals(list: readonly Turn[]) {
  const t = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, tools: 0 }
  for (const turn of list) {
    t.input += turn.input
    t.output += turn.output
    t.cacheRead += turn.cacheRead
    t.cacheWrite += turn.cacheWrite
    t.tools += turn.tools
  }
  const read = t.input + t.cacheRead + t.cacheWrite
  return { ...t, cacheRate: read === 0 ? 0 : Math.round((100 * t.cacheRead) / read) }
}

// The text summary, for /cout and for sessions that draw nothing (claude -p)
async function summary($: EngineInterface): Promise<string> {
  const list = await read($, turns)
  const refused = await read($, refusedBookings)
  if (list.length === 0) {
    return 'Aucun tour terminé dans cette session, ' + refused + ' réservation(s) refusée(s).'
  }
  const t = totals(list)
  const subagents = list.filter(turn => turn.isSubagent).length
  return (
    list.length + ' tour(s) dont ' + subagents + ' de sous-agent(s) : ' +
    t.input + ' tokens en entrée, ' + t.output + ' en sortie, ' +
    t.cacheRead + " lus depuis le cache (" + t.cacheRate + " % de l'entrée), " +
    t.tools + " appel(s) d'outils, " + refused + ' réservation(s) refusée(s).'
  )
}

const column = (value: number | string, width: number) => String(value).padStart(width)

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'cout',
      description: 'Ouvre le compteur de tokens de la session Escale',
      immediate: true,
    })
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    toolsOfTurn = 0
    return next(e)
  })

  // Count the calls of the main turn; subagents have their own turns
  on('tool.call', async ($, e, next) => {
    if (!('agentId' in e) || e.agentId === undefined) toolsOfTurn += 1
    return next(e)
  })

  // Guard: book_hotel cannot be undone, so ask first
  on('tool.call', { tool: BOOK_HOTEL }, async ($, e, next) => {
    const hotel = 'hotel' in e ? String(e.hotel) : 'hôtel inconnu'
    const city = 'city' in e ? String(e.city) : 'ville inconnue'
    const nights = 'nights' in e ? String(e.nights) : '?'
    let answer = NO
    try {
      answer = await $.ui.ask(
        'Escale veut réserver ' + hotel + ' à ' + city + ' pour ' + nights + ' nuit(s). Confirmer ?',
        [YES, NO],
      )
    } catch {
      // Question dismissed, or claude -p with nobody to ask: refuse
    }
    if (answer !== YES) {
      await update($, refusedBookings, n => n + 1)
      return { deny: "L'utilisateur a refusé cette réservation. Ne la relance pas sans lui demander." }
    }
    return next(e)
  }).catch(($, e, next) =>
    // If the guard itself fails, close: no booking without a confirmation
    next.called ? next(e) : { deny: "compteur-escale : la confirmation a échoué, rien n'a été réservé." },
  )

  // End of turn: record what it cost
  on('turn.complete', async ($, e, next) => {
    if (e.usage) {
      const isSubagent = e.agentId !== undefined
      const turn: Turn = {
        input: e.usage.input_tokens,
        output: e.usage.output_tokens,
        cacheRead: e.usage.cache_read_input_tokens,
        cacheWrite: e.usage.cache_creation_input_tokens,
        tools: isSubagent ? 0 : toolsOfTurn,
        seconds: Math.round(e.durationMs / 1000),
        isSubagent,
      }
      await update($, turns, list => [...list, turn].slice(-50))
    }
    return next(e)
  })

  on('command.run', { command: 'cout' }, async $ => {
    // In a terminal or the Desktop app, the panel; elsewhere, the text is enough
    await $.ui.open({ id: PANE, title: 'Compteur Escale' }).catch(() => undefined)
    return { text: await summary($) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, turns)
    const refused = await read($, refusedBookings)
    const t = totals(list)
    const latest = list.slice(-8)
    const first = list.length - latest.length

    return (
      <Box flexDirection="column">
        <Box key="totals">
          <Text bold>
            Session : {t.input + t.cacheRead + t.cacheWrite} en entrée, {t.output} en sortie, cache {t.cacheRate} %
          </Text>
        </Box>
        <Box key="refused">
          <Text dimColor>
            {t.tools} appel(s) d'outils · {refused} réservation(s) refusée(s)
          </Text>
        </Box>
        <Text dimColor>{'  tour   entrée   sortie  cache lu  outils     s'}</Text>
        {latest.map((turn, i) => (
          <Box key={'turn-' + (first + i)}>
            <Text dimColor={turn.isSubagent}>
              {column((turn.isSubagent ? 'a' : '#') + (first + i + 1), 6)}
              {column(turn.input, 9)}
              {column(turn.output, 9)}
              {column(turn.cacheRead, 10)}
              {column(turn.tools, 8)}
              {column(turn.seconds, 6)}
            </Text>
          </Box>
        ))}
        {list.length === 0 && <Text dimColor>Aucun tour terminé pour l'instant.</Text>}
      </Box>
    )
  })
}
