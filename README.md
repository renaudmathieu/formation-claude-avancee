# Escale

Assistant de déplacement professionnel, construit pas à pas avec Claude Code pendant la formation « Claude Avancé » (5 jours, 12 sections). Escale est une entreprise fictive : sa politique de voyage, ses justificatifs et ses hôtels sont inventés.

Chaque section de la formation correspond à un **checkpoint**, une branche `etape/NN-nom` qui contient le projet tel qu'il doit être à la fin de la section. Vous partez du checkpoint précédent, vous faites l'exercice, et vous pouvez comparer avec le checkpoint suivant ou repartir de lui.

**Jamais fait de Python ?** Commencez par [le rappel Python](docs/python-express.md), 5 minutes suffisent.

## Installation

Il faut seulement [`uv`](https://docs.astral.sh/uv/getting-started/installation/) : il télécharge lui-même Python si besoin. Pour la section 7 (le mod), il faut aussi Claude Code (`claude`).

```bash
uv sync
cp .env.example .env   # puis renseigner les clés données par le formateur
```

Sous Windows PowerShell ou en invite de commandes, `cp` peut être remplacé par `copy`.

Le fichier `.env` contient `ANTHROPIC_API_KEY` (obligatoire dès la section 1) et `VOYAGE_API_KEY` (section 9, facultative : sans elle la recherche est par mots-clés seuls). Il n'est jamais suivi par git : ne l'ajoutez pas à un commit.

## Vérifier que tout marche

```bash
uv run pytest -q
uv run ruff check .
```

Les tests n'appellent ni l'API ni le réseau : ils passent sans clé. Le nombre attendu dépend du checkpoint, voir le tableau plus bas.

## Commandes

| Commande | Ce qu'elle fait | Depuis |
| --- | --- | --- |
| `uv run python -m escale ask "question"` | Une question, une réponse, le coût de l'appel | 00 |
| `uv run python -m escale chat` | Une conversation, avec image possible | 02 |
| `uv run python -m escale agent "tâche"` | L'agent prépare un déplacement avec ses outils (`--effort`, `--budget`) | 04 |
| `uv run python -m escale check note.md` | Vérifie une note de frais contre la politique | 05 |
| `uv run python -m scripts.compare_models` | Compare trois modèles sur les mêmes tâches | 01 |
| `uv run python -m evals.run v2` | Taux de réussite d'une version du prompt d'extraction | 03 |
| `uv run python -m evals.run_rag` | Recall@5 de la recherche, trois versions (`--k 1`, `--claude-context`) | 09 |
| `uv run python -m scripts.cout_par_question` | Coût de chaque question, lu dans `.escale/trace.jsonl` | 10 |
| `uv run python -m escale.mcp_server` | Le serveur MCP d'Escale (stdio, déclaré dans `.mcp.json`) | 06 |
| `uv run python -m escale.transport_server` | Le serveur de démonstration trains et hôtels (HTTP) | 06 |
| `claude --plugin-dir ./outils/compteur-escale` | Claude Code avec le mod (panneau `/cout`, garde de réservation) | 07 |

Chaque appel à `ask`, `chat`, `agent` ou `check` consomme du crédit API.

## Les checkpoints

Pour aller à un checkpoint : `git switch etape/04-tools`. Pour récupérer seulement les tests d'une section dans votre copie : `git checkout etape/04-tools -- tests/test_agent.py`. Ces tests sont le contrat de la section : ils échouent sans le code de la section et passent avec.

| Branche | Section | Ce que le checkpoint ajoute | Tests attendus |
| --- | --- | --- | --- |
| `etape/00-depart` | 0 | Le point de départ : `escale/config.py` (modèles, prix, coût d'un appel, `verifier()`), la politique de voyage et les dix justificatifs | `10 passed, 9 skipped` |
| `etape/01-premier-appel` | 1 | `scripts/compare_models.py` : trois modèles, mêmes tâches, tokens, durée et coût | `15 passed, 9 skipped` |
| `etape/02-client` | 2 | Client robuste : `ask`, `stream`, `with_retry` (jamais sur un 400), `read_ticket`, `chat` complété | `37 passed, 1 skipped` |
| `etape/03-prompts` | 3 | Extraction en sortie structurée, prompts v1 et v2, `evals/run.py` | `51 passed, 1 skipped` |
| `etape/04-tools` | 4 | La boucle d'agent, les tools (politique, fichiers, météo), le prompt système, `agent` | `91 passed` |
| `etape/05-claude-code` | 5 | `CLAUDE.md`, réglages, hooks PreToolUse (commandes destructrices), PostToolUse (ruff) et Stop (tests verts), skill `/ajouter-tool`, commande `check` | `125 passed` |
| `etape/06-mcp` | 6 | Serveur MCP (recherche, ressource, `book_hotel`), client MCP, outils différés (`ESCALE_MCP_DIFFERE`), page piégée, `docs/contexte-mcp.md` | `152 passed` |
| `etape/07-mod` | 7 | Mod `outils/compteur-escale` : panneau `/cout` et garde sur la réservation | `153 passed` |
| `etape/08-agent` | 8 | Budget en dollars, confirmation humaine, journal d'événements, données non fiables balisées, effort, le même agent avec le Claude Agent SDK (`escale/agent_sdk.py`) | `179 passed, 2 skipped` |
| `etape/09-rag` | 9 | Politique élargie à 11 pages, recherche hybride (BM25, Voyage, RRF), citations vérifiées, `evals/run_rag.py` | `224 passed, 2 skipped` |
| `etape/10-prod` | 10 | Journal JSON par appel, coût par question, cache, routage, disjoncteur, quota, prompts versionnés, revue headless en CI, lot back-office (`escale/batch.py`) | `270 passed, 2 skipped` |
| `etape/11-final` | 11 | `docs/projet-final.md` (trois variantes, spécification d'une page) et ce README | `275 passed, 2 skipped` |

Les deux tests ignorés à partir de la section 8 demandent le SDK : `uv sync --extra sdk` les active.

La section 7 passe par `claude plugin validate outils/compteur-escale` et `claude plugin test outils/compteur-escale` : ces deux commandes ne comptent pas dans le résultat de `pytest`, et n'appellent pas l'API.

## Contenu du projet

| Chemin | Rôle |
| --- | --- |
| `escale/llm.py` | Le seul fichier qui appelle l'API de Claude |
| `escale/config.py` | Le seul endroit où figurent un modèle, un prix ou un réglage |
| `escale/agent.py` | La boucle d'agent et ses gardes, sans rien savoir du métier |
| `escale/assistant.py` | Le prompt système et la liste des tools |
| `escale/tools/` | Les tools : politique, fichiers, météo, réservation |
| `escale/rag.py` | La recherche dans la politique et les réponses citées |
| `escale/trace.py`, `quota.py`, `resilience.py` | Journal des appels, quota par utilisateur, disjoncteur |
| `escale/mcp_server.py` | Escale comme serveur MCP |
| `outils/compteur-escale/` | Le mod Claude Code (TypeScript) |
| `data/politique-voyage/` | La politique de voyage de l'entreprise fictive (11 pages) |
| `data/justificatifs/` | Dix justificatifs de dépenses fictifs |
| `prompts/` | Les prompts, un fichier par version |
| `evals/` | Les jeux d'évaluation et leurs scripts |
| `docs/` | Le rappel Python, la page piégée, le projet final |
| `sortie/` | Les fichiers générés par Escale |
| `tests/` | Les tests, qui s'appuient sur un faux client (`tests/fakes.py`) |

## Variables d'environnement

| Variable | Effet | Défaut |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Clé de l'API de Claude | aucune, obligatoire |
| `VOYAGE_API_KEY` | Clé des embeddings (section 9) | aucune : recherche par mots-clés |
| `ESCALE_MODEL` | Modèle de travail de tous les exercices | Haiku dans `.env.example` ; sans la variable, Sonnet |
| `ESCALE_EFFORT` | Effort de réflexion de l'agent (`low` à `max`) | `high` |
| `ESCALE_BUDGET_USD` | Budget d'une tâche de l'agent | `0.50` |
| `ESCALE_QUOTA_USD` | Quota journalier par utilisateur | `1.00` |
| `ESCALE_USER` | Nom de l'utilisateur dans le journal et le quota | `anonyme` |
| `ESCALE_POLITIQUE` | Dossier de politique de remplacement | `data/politique-voyage/` |
| `ESCALE_METEO` | `simule` : météo hors ligne | service Open-Meteo |
| `ESCALE_MCP_URL` | Adresse du serveur MCP distant de l'agent | `http://127.0.0.1:8765/mcp` |

## En cas de panne

- **`uv: command not found`** : installer `uv` (lien plus haut), puis ouvrir un nouveau terminal.
- **`ANTHROPIC_API_KEY manquante`** : le fichier `.env` doit être à la racine du dépôt et contenir la clé donnée par le formateur. **Clé refusée** : recopier la clé en entier, sans espace ni guillemet.
- **API injoignable** : vérifier le réseau ou le proxy de l'entreprise. Les tests, eux, passent hors ligne.
- **Réponse « Escale est momentanément indisponible »** (section 10) : l'API ne répond pas, ou le disjoncteur est ouvert. Réessayer dans une demi-minute.
- **« Quota journalier atteint »** (section 10) : augmenter `ESCALE_QUOTA_USD` ou changer `ESCALE_USER`. Le quota se lit dans `.escale/trace.jsonl`.
- **« Budget de la tâche atteint »** (section 8) : relancer avec `--budget 1.0`, ou réduire la tâche.
- **Le service météo ne répond pas** : ajouter `ESCALE_METEO=simule` dans `.env`.
- **`[mcp] Serveur injoignable`** : normal si `uv run python -m escale.transport_server` n'est pas lancé dans un autre terminal ; l'agent continue sans les trains et hôtels.
- **Pas de `VOYAGE_API_KEY`** : la recherche dans la politique reste utilisable, par mots-clés. `evals.run_rag` utilise alors des embeddings simulés hors ligne, qui ne voient que l'orthographe.
- **`claude plugin validate` échoue** : mettre Claude Code à jour (l'API des mods est en accès anticipé) et relancer.
- **Un test est rouge après un `git checkout etape/NN -- tests/...`** : c'est voulu, c'est l'exercice de la section. Le code à écrire est décrit dans le support de la section.
- **Un test est rouge et vous n'avez rien touché** : `git status` pour voir ce qui a changé, puis `uv sync` au cas où une dépendance manque.
