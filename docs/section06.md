# Section 6 : Doc42 comme serveur MCP

Checkpoint `etape/06-mcp`. Le serveur est `doc42/mcp_server.py` : une façade sur `doc42.outils`, en transport stdio.

| Primitive | Nom | Nom côté Claude Code |
|---|---|---|
| Outil (lecture) | `chercher_documents(requete, limite)` | `mcp__doc42__chercher_documents` |
| Outil (écriture) | `creer_fiche(titre, contenu)` | `mcp__doc42__creer_fiche` |
| Ressource | `doc42://documents` (liste JSON id + titre) | `@doc42:doc42://documents` |

## Installer et connecter

SDK Python officiel `mcp` 2.x, déjà dans les dépendances du projet (FastMCP y est devenu `MCPServer` : `from mcp.server.mcpserver import MCPServer`). À la racine du dépôt :

```bash
uv sync
claude mcp add doc42 -- uv run python -m doc42.mcp_server
```

Les options de `claude mcp add` (`--scope`, `--env`, `--transport`) se placent avant le nom, la commande du serveur après `--`. La syntaxe a changé plusieurs fois : vérifier avec `claude mcp add --help` et reporter la forme courante dans le registre de fraîcheur. En session, `/mcp` doit lister `doc42` et ses deux outils.

Lancer Claude Code depuis la racine du dépôt : `uv run` y trouve le projet et `python -m` y trouve le paquet `doc42`. Les variables `DOC42_CORPUS` et `DOC42_FICHES` déplacent le corpus et le dossier des fiches (`claude mcp add --env DOC42_FICHES=/chemin doc42 -- ...`).

Les journaux du serveur (un par appel d'outil) sortent sur stderr : c'est là qu'on vérifie qu'une question en langage naturel a bien déclenché un appel. Jamais de `print()` dans le serveur, stdout est le canal du protocole.

## Règle de permission (étape 6)

Ajouter l'outil d'écriture à la liste `deny` de `.claude/settings.json` (créé en section 5) :

```json
{
  "permissions": {
    "deny": ["mcp__doc42__creer_fiche"]
  }
}
```

Viser l'outil, pas le serveur : `mcp__doc42` ou `mcp__doc42__*` bloqueraient aussi la recherche. Une règle `deny` l'emporte sur `ask` et `allow`. Vérification : relancer Claude Code, demander une fiche, l'appel doit être refusé sans question. En section 7, un mod remplace cette interdiction par une confirmation.

## Injection indirecte (étape 7)

On ne copie jamais le piège dans `corpus/` (règle du `CLAUDE.md`) : on prépare un corpus temporaire et on déclare un second serveur qui le lit.

```bash
mkdir -p /tmp/corpus-piege && cp corpus/*.md corpus_pieges/note_fournisseur_piegee.md /tmp/corpus-piege/
claude mcp add --env DOC42_CORPUS=/tmp/corpus-piege doc42-piege -- uv run python -m doc42.mcp_server
# dans Claude Code : « Que dit la note du fournisseur DataPlus ? »
claude mcp remove doc42-piege
```

Attention : ce second serveur s'appelle `doc42-piege`, ses outils sont donc `mcp__doc42-piege__...` et la règle `deny` de l'étape 6 ne les vise pas. Ajoutez `mcp__doc42-piege__creer_fiche` à la liste `deny` le temps de l'exercice, ou observez justement qu'une règle écrite pour un nom de serveur ne protège pas un autre nom.

La recherche encadre chaque extrait dans `<document id="..."> ... </document>` et les instructions du serveur rappellent que le contenu d'un document est une donnée. Ce n'est qu'un signal : la protection qui tient, c'est la règle `deny`.

## Tests

```bash
uv run pytest tests/test_section06.py -v
```
