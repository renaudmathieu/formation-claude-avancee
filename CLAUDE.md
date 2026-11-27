# Escale : assistant de déplacement professionnel

## Commandes
- Installer : `uv sync`. Tests : `uv run pytest -q`. Lint : `uv run ruff check .`
- Lancer : `uv run python -m escale chat`, `agent "tâche"`, `ask "question"`
- Vérifier une note de frais : `uv run python -m escale check <note.md>`

## Architecture
- `escale/llm.py` est le seul fichier qui appelle la Messages API.
- `escale/config.py` est le seul endroit où figurent un identifiant de modèle ou un prix.
- `escale/agent.py` contient la boucle, sans rien savoir du métier.
- `escale/assistant.py` définit le prompt système et la liste des tools.
- `escale/tools/` contient les tools. Une panne se signale par `ToolError`.
  Pour en ajouter un : `/ajouter-tool`.
- `escale/extraction.py` lit un justificatif. `escale/check.py` le compare à la politique.
- `escale/mcp_server.py` expose la recherche, la ressource `escale://politique` et `book_hotel`
  (stdio, déclaré dans `.mcp.json`). `escale/mcp_client.py` charge les tools d'un serveur distant,
  `escale/transport_server.py` est le serveur de démonstration (trains, hôtels), lancé à part.
- `book_hotel` est définitif : le mod `outils/compteur-escale` demande confirmation avant
  `mcp__escale__book_hotel` (`claude --plugin-dir ./outils/compteur-escale`, panneau `/cout`).
- La politique de voyage est dans `data/politique-voyage/` (une page Markdown par sujet),
  ou le dossier `ESCALE_POLITIQUE` s'il est défini.

## Règles métier (à faire respecter dans le code et dans les réponses)
- Toute règle appliquée cite sa page de la politique, par exemple « page hebergement ».
- Une information manquante est déclarée manquante : on ne la devine jamais
  (par exemple la ville d'un hôtel, qui change le plafond).
- Une réservation demande une confirmation explicite de l'utilisateur avant de partir.
- Un plafond se lit dans la politique, jamais dans le code : si la politique change, le verdict change.

## Règles de l'API (à vérifier, pas à deviner)
- L'API ne garde aucun état : chaque appel renvoie tout l'historique.
- On ajoute `response.content` entier à l'historique, blocs de thinking compris.
- `stop_reason` pilote la boucle : `tool_use`, `pause_turn`, `end_turn`, `max_tokens`, `refusal`.
- Claude ne connaît pas la date : elle est donnée dans le prompt système.
- Tous les `tool_result` d'une réponse repartent dans un seul message utilisateur.
- On lit le texte avec `text_of`, jamais avec `content[0].text`.

## Conventions
- Les tests utilisent `tests/fakes.py` : jamais d'appel réseau ni de clé dans un test.
- Les tools d'écriture restent limités à `sortie/` (`resolve_inside`), et chaque limite a un test.
- Commentaires, docstrings et messages de commit en anglais, textes affichés en français.
- Lancer `uv run pytest -q` avant de proposer un commit.

## À ne pas faire
- Les règles qui ne cèdent jamais sont dans `.claude/settings.json` et `.claude/hooks/` : ici on oriente.
- Ne jamais lire ni afficher `.env`, ne jamais écrire une clé dans un fichier suivi.
- Ne pas lancer l'agent ni `check` sans demander : chaque exécution consomme du crédit API.
- Ne pas faire de `git push`.
