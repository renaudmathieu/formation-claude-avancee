// Mod « compteur-doc42 » : mesurer et garder ce que Claude Code fait avec Doc42.
// - Compte les tokens de chaque tour (entrée, sortie, cache) et les appels d'outils.
// - /cout ouvre un panneau avec les derniers tours et les totaux de la session.
// - Retient chaque appel à creer_fiche du serveur MCP Doc42 jusqu'à une
//   confirmation explicite, et refuse si la question ne peut pas être posée.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Tour } from '../types'

const tours = atom({ plugin: 'compteur-doc42', key: 'tours' } as const, [])
const fichesRefusees = atom({ plugin: 'compteur-doc42', key: 'fichesRefusees' } as const, 0)

const PANE = 'compteur'
// L'outil d'écriture de la section 6, tel que Claude Code le nomme
const CREER_FICHE = 'mcp__doc42__creer_fiche'
const OUI = 'Créer la fiche'

// Appels d'outils du tour principal en cours (une variable suffit : un tour à la fois)
let outilsDuTour = 0

function totaux(liste: readonly Tour[]) {
  const t = { entree: 0, sortie: 0, cacheLu: 0, cacheEcrit: 0, outils: 0 }
  for (const tour of liste) {
    t.entree += tour.entree
    t.sortie += tour.sortie
    t.cacheLu += tour.cacheLu
    t.cacheEcrit += tour.cacheEcrit
    t.outils += tour.outils
  }
  const lus = t.entree + t.cacheLu + t.cacheEcrit
  return { ...t, tauxCache: lus === 0 ? 0 : Math.round((100 * t.cacheLu) / lus) }
}

// Le résumé texte, pour /cout et pour les sessions qui ne dessinent rien (claude -p)
async function resume($: EngineInterface): Promise<string> {
  const liste = await read($, tours)
  const refus = await read($, fichesRefusees)
  if (liste.length === 0) return 'Aucun tour terminé dans cette session, ' + refus + ' fiche(s) refusée(s).'
  const t = totaux(liste)
  return (
    liste.length + ' tour(s) : ' + t.entree + ' tokens en entrée, ' + t.sortie + ' en sortie, ' +
    t.cacheLu + ' lus depuis le cache (' + t.tauxCache + ' % de l\'entrée), ' +
    t.outils + ' appel(s) d\'outils, ' + refus + ' fiche(s) refusée(s).'
  )
}

const colonne = (valeur: number | string, largeur: number) => String(valeur).padStart(largeur)

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'cout',
      description: 'Ouvre le compteur de tokens de la session Doc42',
      immediate: true,
    })
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    outilsDuTour = 0
    return next(e)
  })

  // Compte les appels du tour principal ; ceux des sous-agents ont leur propre tour
  on('tool.call', async ($, e, next) => {
    if (!('agentId' in e) || e.agentId === undefined) outilsDuTour += 1
    return next(e)
  })

  // Garde : creer_fiche écrit un fichier, on demande avant
  on('tool.call', { tool: CREER_FICHE }, async ($, e, next) => {
    const titre = 'titre' in e ? String(e.titre) : 'sans titre'
    let reponse = 'Refuser'
    try {
      reponse = await $.ui.ask('Doc42 veut créer la fiche « ' + titre + ' ». La créer ?', [OUI, 'Refuser'])
    } catch {
      // Question écartée, ou claude -p sans personne à qui demander : on refuse
    }
    if (reponse !== OUI) {
      await update($, fichesRefusees, n => n + 1)
      return { deny: "L'utilisateur a refusé la création de cette fiche. Ne la recrée pas sans lui demander." }
    }
    return next(e)
  }).catch(($, e, next) =>
    // Si la garde elle-même échoue, on ferme : pas de fiche sans confirmation
    next.called ? next(e) : { deny: "compteur-doc42 : la confirmation a échoué, la fiche n'a pas été créée." },
  )

  // Fin de tour : on range ce qu'il a coûté
  on('turn.complete', async ($, e, next) => {
    if (e.usage) {
      const isSousAgent = e.agentId !== undefined
      const tour: Tour = {
        entree: e.usage.input_tokens,
        sortie: e.usage.output_tokens,
        cacheLu: e.usage.cache_read_input_tokens,
        cacheEcrit: e.usage.cache_creation_input_tokens,
        outils: isSousAgent ? 0 : outilsDuTour,
        secondes: Math.round(e.durationMs / 1000),
        isSousAgent,
      }
      await update($, tours, liste => [...liste, tour].slice(-50))
    }
    return next(e)
  })

  on('command.run', { command: 'cout' }, async $ => {
    // Dans un terminal ou le Desktop, le panneau ; ailleurs, le texte suffit
    await $.ui.open({ id: PANE, title: 'Compteur Doc42' }).catch(() => undefined)
    return { text: await resume($) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const liste = await read($, tours)
    const refus = await read($, fichesRefusees)
    const t = totaux(liste)
    const derniers = liste.slice(-8)
    const premier = liste.length - derniers.length

    return (
      <Box flexDirection="column">
        <Box key="totaux">
          <Text bold>
            Session : {t.entree + t.cacheLu + t.cacheEcrit} en entrée, {t.sortie} en sortie, cache {t.tauxCache} %
          </Text>
        </Box>
        <Box key="refus">
          <Text dimColor>
            {t.outils} appel(s) d'outils · {refus} fiche(s) refusée(s)
          </Text>
        </Box>
        <Text dimColor>{'  tour   entrée   sortie  cache lu  outils     s'}</Text>
        {derniers.map((tour, i) => (
          <Box key={'tour-' + (premier + i)}>
            <Text dimColor={tour.isSousAgent}>
              {colonne((tour.isSousAgent ? 'a' : '#') + (premier + i + 1), 6)}
              {colonne(tour.entree, 9)}
              {colonne(tour.sortie, 9)}
              {colonne(tour.cacheLu, 10)}
              {colonne(tour.outils, 8)}
              {colonne(tour.secondes, 6)}
            </Text>
          </Box>
        ))}
        {liste.length === 0 && <Text dimColor>Aucun tour terminé pour l'instant.</Text>}
      </Box>
    )
  })
}
