# Prompts d'extraction : journal des versions

Chaque version est mesurée sur `evals/attendu.json` (dix documents) avec
`uv run python evals/lancer.py`. Un changement à la fois, une mesure à chaque fois.
Les taux dépendent du modèle et du jour : notez toujours le modèle et la date.

| Version | Changement | Modèle | Prefill | Tentatives | Taux | Date |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | Paragraphe libre | défaut | non | 1 | ../10 | |
| v2 | Balises, conventions du jeu, schéma, un exemple | défaut | non | 1 | ../10 | |
| v2 sans exemple | `--sans-exemple` | défaut | non | 1 | ../10 | |
| v2 + prefill | `--prefill --modele rapide` | rapide | oui | 1 | ../10 | |
| v2 + relance | `--tentatives 3` | défaut | non | 3 | ../10 | |

## v2

Pourquoi : la v1 laisse le modèle choisir la forme et le sens. Rien n'y fixe
le format des dates ni celui des montants, rien n'interdit le texte autour du
JSON, rien ne dit quelle date est « la » date d'un document, ni qu'une date
d'action ou un jalon n'est pas une échéance de paiement. Ce que vous avez
observé à l'étape 1 sur trois documents :

Ce qui change :

- Structure en balises : `<role>`, `<context>`, `<instructions>` numérotées,
  `<constraints>`, `<examples>`.
- Les conventions du jeu de test sont écrites dans le prompt (quelle date,
  quelles parties, ce qui est ou n'est pas une échéance). Sans elles, on mesure
  un malentendu et pas la qualité du prompt.
- Le schéma JSON est inséré tel quel dans les contraintes.
- Un exemple fictif (Omega Imprimerie), qui n'emprunte rien au jeu de test.
- Une règle explicite : document sans échéance, `"echeances": []`.

Mesure : v1 ../10, v2 ../10 (à reporter dans le tableau). Échecs restants :

## v1

Premier jet, sans structure, conservé pour la comparaison.

## Notes

- Le prefill (`--prefill`) est refusé par une erreur 400 sur les modèles
  récents (famille 4.6 et suivantes) : mesurez-le avec un modèle qui l'accepte.
  Il contraint le format, pas le contenu.
- La relance (`--tentatives 3`) mesure le prompt plus son rattrapage. Le taux
  monte, le coût aussi : comparez les deux chiffres, pas seulement le second.
