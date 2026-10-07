# Doc42 : le fil rouge de la formation « Maîtrisez l'écosystème Anthropic de bout en bout »

Doc42 est un assistant d'analyse de documents internes pour Hexalis, une société fictive. On le construit section après section : premier appel à l'API, client robuste, prompts évalués, outils, Claude Code, serveur MCP, mod Claude Code, agent, RAG, mise en production, projet final.

Ce dépôt est le **dépôt solution du formateur** : il contient les énoncés (`exercices/`), les corrigés (`solutions/`), les contrats de test (`tests/`) et une branche par checkpoint. Les supports de cours sont dans Notion.

## Installer

Prérequis : Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+ pour la section 6 (partie TypeScript) et la section 7 (vérification de types du mod), Claude Code 2.1.287+ pour la section 7.

```bash
uv sync
cp .env.example .env   # puis renseigner ANTHROPIC_API_KEY (inutile pour les tests)
```

## Travailler une section

Chaque section NN a trois fichiers : `exercices/sectionNN.py` (les fonctions à compléter, énoncés en docstring), `solutions/sectionNN.py` (le corrigé commenté) et `tests/test_sectionNN.py` (le contrat).

```bash
uv run pytest tests/test_section04.py -v               # contre vos exercices : rouge au départ
uv run pytest tests/test_section04.py -v --solutions   # contre le corrigé (formateur)
uv run pytest tests/test_section04.py --reel           # ajoute un test contre la vraie API (payant)
```

Les tests tournent **hors ligne, sans clé API et sans quota** : ils utilisent un faux client (`tests/fakes.py`) qui enregistre ce qu'on lui envoie. On évalue le code du stagiaire, pas la réponse de Claude.

`doc42/` contient le socle de l'application, donné dès le départ pour que personne ne reste bloqué : `config.py` (seul endroit où figurent les identifiants de modèles et les tarifs, pendant du registre de fraîcheur Notion), `corpus.py`, `client.py` (le corrigé de la section 2) et `outils.py` (les outils `chercher_documents` et `creer_fiche`). Chaque checkpoint y ajoute la pièce produite par sa section.

## Les checkpoints

| Branche | Section | Ce qu'elle ajoute | Tests du contrat |
| --- | --- | --- | --- |
| `main` = `etape/00-depart` | | Socle `doc42/`, corpus, énoncés, corrigés et contrats de toutes les sections | |
| `etape/01-premier-appel` | 1. Fondamentaux | Exercices complétés, `scripts/comparer_modeles.py`, `NOTES.md` | 29 |
| `etape/02-client` | 2. API Messages | Client robuste : multi-tours, streaming, PDF, reprise | 6 |
| `etape/03-prompts` | 3. Prompt engineering | `doc42/extraction.py`, prompts versionnés, `evals/lancer.py` | 54 |
| `etape/04-tools` | 4. Tool use | `doc42/boucle.py` : la boucle d'outils de référence | 33 |
| `etape/05-claude-code` | 5. Claude Code | `CLAUDE.md`, `.claude/settings.json`, `python -m doc42 resume` | 20 |
| `etape/06-mcp` | 6. MCP | `doc42/mcp_server.py`, règle `deny` sur `creer_fiche` | 14 |
| `etape/07-mod` | 7. Mods | Le mod `outils/compteur-doc42/` (panneau `/cout`, garde de `creer_fiche`) | 5 (mod) |
| `etape/08-agent` | 8. Agents | `doc42/agent.py` : bornes, budget, confirmation humaine | 26 |
| `etape/09-rag` | 9. RAG | `doc42/rag.py` : BM25, vecteurs, fusion, citations vérifiées | 26 |
| `etape/10-prod` | 10. Production | `doc42/observabilite.py`, `garde_fous.py`, `prompts.py` | 25 |
| `etape/11-final` | 11. Projet final | Variante de référence `doc42/variantes/analyseur.py`, `docs/projet-final.md` | 33 |

À chaque checkpoint, les exercices des sections déjà faites sont complétés : `uv run pytest tests/test_sectionNN.py` passe pour toute section NN inférieure ou égale au checkpoint. La section 12 n'a pas de checkpoint.

## Préparer le dépôt des stagiaires

Les stagiaires reçoivent `main` **sans** le dossier `solutions/` :

```bash
git clone --single-branch --branch main <ce dépôt> doc42 && cd doc42
git rm -r -q solutions && git commit -m "Dépôt stagiaires" && git remote set-url origin <dépôt stagiaires>
```

Les tests restent utilisables sans `solutions/` (l'option `--solutions` n'est alors plus disponible). Le jeu d'évaluation de la section 3 (`evals/attendu.json`) est dans `main` car le contrat le lit : l'énoncé demande d'écrire le sien avant de le comparer.

## Points à vérifier avant chaque session

- Les identifiants de modèles et les tarifs de `doc42/config.py` reprennent le registre de fraîcheur du 1er septembre 2026 : à revérifier.
- Section 3 : le préremplissage de la réponse (prefill) n'est plus accepté par tous les modèles récents ; l'énoncé le fait mesurer avec `MODELE_RAPIDE`.
- Section 6 : le SDK `mcp` 2.x a renommé FastMCP en `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
- Section 7 : `claude plugin validate outils/compteur-doc42` et `claude plugin test outils/compteur-doc42` sur `etape/07-mod`.
