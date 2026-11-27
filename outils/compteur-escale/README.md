# Mod `compteur-escale`

Le mod de la section 7 : il mesure et garde ce que Claude Code fait avec Escale.

- **`/cout`** ouvre un panneau avec les tokens de chaque tour (entrée, sortie, cache lu), le taux de cache de la session, les appels d'outils, et les tours des sous-agents à part (lignes `a1`, `a2`...). Là où rien ne se dessine (`claude -p`, panneau de chat de VS Code), la commande répond le même résumé en texte.
- **Une garde sur `mcp__escale__book_hotel`** : chaque réservation attend une confirmation explicite (« Réserver » ou « Refuser ») ; un refus est compté et renvoyé à Claude comme consigne ; si la question ne peut pas être posée, la réservation est refusée (la garde échoue du côté sûr).

## Audit en une phrase

> Ce mod a le droit de lire l'usage de chaque tour et d'intercepter `mcp__escale__book_hotel`, et seulement de cela : il n'écrit aucun fichier, ne lance aucun processus et ne touche pas au réseau.

## Utiliser

Depuis la racine du dépôt, avec le serveur MCP de la section 6 (déclaré dans `.mcp.json` sous le nom `escale`) :

```bash
claude --plugin-dir ./outils/compteur-escale
```

`.claude/settings.json` doit porter une règle `allow` sur `mcp__escale__book_hotel` (et plus la règle `deny` de la section 6) : le hook `tool.call` du mod passe avant la vérification des permissions, donc avec le `deny` la réservation serait refusée même après « Réserver », et sans règle Claude Code poserait sa propre question après celle du mod. Retirer le mod sans retirer cet `allow` laisse l'outil de réservation sans garde.

## Vérifier

```bash
claude plugin validate outils/compteur-escale
claude plugin test outils/compteur-escale
```

Aucune de ces commandes n'appelle l'API. Testé le 26 novembre 2026 sur Claude Code 2.1.330 : validation passée (avec deux avertissements de l'annuaire public, licence et icône, sans effet pour un usage local), 6 tests verts. L'API des mods est en accès anticipé : relancer ces deux commandes après chaque mise à jour de Claude Code.
