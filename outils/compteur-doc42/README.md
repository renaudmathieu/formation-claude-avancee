# Mod `compteur-doc42`

Le mod de la section 7 : il mesure et garde ce que Claude Code fait avec Doc42.

- **`/cout`** ouvre un panneau avec les tokens de chaque tour (entrée, sortie, cache lu), le taux de cache de la session, les appels d'outils, et les tours des sous-agents à part. Là où rien ne se dessine (`claude -p`, panneau de chat de VS Code), la commande répond le même résumé en texte.
- **Une garde sur `mcp__doc42__creer_fiche`** : chaque création de fiche attend une confirmation explicite (« Créer la fiche » ou « Refuser ») ; un refus est compté et renvoyé à Claude comme consigne ; si la question ne peut pas être posée, la fiche est refusée.

## Utiliser

Claude Code **2.1.287 ou plus récent**, le serveur MCP de la section 6 ajouté sous le nom `doc42`, depuis la racine du dépôt :

```bash
claude --plugin-dir ./outils/compteur-doc42
```

`.claude/settings.json` porte une règle `allow` sur `mcp__doc42__creer_fiche` : le hook `tool.call` du mod passe avant la vérification des permissions, donc avec le `deny` de la section 6 la fiche serait refusée même après « Créer la fiche », et sans règle Claude Code poserait sa propre question après celle du mod. Retirer le mod sans retirer cet `allow` laisse l'outil d'écriture sans garde.

## Vérifier

```bash
claude plugin validate outils/compteur-doc42
claude plugin test outils/compteur-doc42
```

Testé le 7 octobre 2026 sur Claude Code 2.1.292 : validation passée, 5 tests verts. L'API des mods est en accès anticipé : relancer ces deux commandes après chaque mise à jour de Claude Code. Le code commenté et la démarche sont sur la page Notion de la section 7.
