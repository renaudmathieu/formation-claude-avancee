// Un tour terminé : ce qu'il a coûté, en tokens, et ce qu'il a fait
export type Tour = {
  // Tokens d'entrée hors cache
  entree: number
  // Tokens générés par le modèle
  sortie: number
  // Tokens d'entrée servis par le cache de prompt
  cacheLu: number
  // Tokens d'entrée écrits dans le cache de prompt
  cacheEcrit: number
  // Appels d'outils pendant le tour
  outils: number
  // Durée du tour, en secondes
  secondes: number
  // true pour le tour d'un sous-agent
  isSousAgent: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'compteur-doc42': {
      tours: Tour[]
      fichesRefusees: number
    }
  }
}
