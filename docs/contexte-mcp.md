# Le coût caché des définitions d'outils

Brancher un serveur MCP prend une ligne. Le vrai sujet, c'est ce qu'il coûte **avant le premier prompt** : chaque outil envoie son nom, sa description et son schéma à chaque requête. Quelques gros serveurs suffisent pour remplir des dizaines de milliers de tokens.

Noms et valeurs vérifiés le 26 novembre 2026 dans la documentation. À relire dans le registre de fraîcheur avant chaque session.

## 1. Mesurer dans Claude Code

1. Lancer `claude` dans le dépôt, sans rien demander, et taper `/context`. Noter la ligne des outils MCP.
2. `/mcp` : nombre d'outils par serveur.
3. Relancer avec `ENABLE_TOOL_SEARCH=false claude` : toutes les définitions sont chargées d'emblée. Refaire `/context` et comparer.

Ce qu'on observe : par défaut, Claude Code **diffère** les outils MCP. `/context` les marque « deferred » ; Claude les retrouve avec son outil de recherche d'outils quand il en a besoin.

| Réglage | Effet |
| --- | --- |
| `ENABLE_TOOL_SEARCH` absent ou `true` | Outils MCP différés, chargés à la demande (défaut) |
| `ENABLE_TOOL_SEARCH=auto` | Chargés d'emblée tant qu'ils pèsent moins de 10 % de la fenêtre de contexte |
| `ENABLE_TOOL_SEARCH=auto:5` | Même chose avec un seuil de 5 % |
| `ENABLE_TOOL_SEARCH=false` | Tout chargé d'emblée |
| `"alwaysLoad": true` sur un serveur (`.mcp.json`) | Ce serveur est toujours chargé, les autres restent différés |

Conclusion de l'atelier : Claude Code règle le problème pour vous. **Votre propre agent, lui, envoie tout**, tant que vous ne faites rien.

## 2. Mesurer dans l'agent Escale

`escale/mcp_client.py` transforme les outils du serveur MCP en outils de l'agent, et `Toolbox.definitions()` les envoie tous à l'API à chaque tour. Pour chiffrer ce que cela coûte, sans consommer de crédit (le comptage de tokens est gratuit) :

```python
import anthropic
from escale import assistant, config

client = anthropic.Anthropic()
box = assistant.build_toolbox()
count = client.messages.count_tokens(
    model=config.default_model(),
    tools=box.definitions(),
    messages=[{"role": "user", "content": "Bonjour"}],
)
print(count.input_tokens)
```

Lancer le serveur (`uv run python -m escale.transport_server`), mesurer, puis recommencer avec `ESCALE_MCP_DIFFERE=1`.

## 3. Les trois leviers

**Recherche d'outils à la demande.** Avec `ESCALE_MCP_DIFFERE=1`, chaque définition MCP porte `"defer_loading": true` et `Toolbox.definitions()` ajoute l'outil serveur `tool_search_tool_bm25_20251119`. L'API ne met pas les outils différés dans le contexte : Claude cherche par mots-clés, l'API charge les quelques outils trouvés. Deux contraintes : l'outil de recherche ne doit jamais être différé, et au moins un outil doit rester chargé (ici les outils locaux), sinon l'API renvoie une erreur 400. Variante par expression régulière : `tool_search_tool_regex_20251119`.

**Programmatic tool calling.** Claude écrit un script qui appelle vos outils dans l'outil d'exécution de code (`code_execution_20260120`), filtre les résultats et ne renvoie que l'utile. On l'active outil par outil avec `"allowed_callers": ["code_execution_20260120"]`. Ce sont surtout les **résultats** intermédiaires qui ne passent plus par le contexte. Limites : incompatible avec `strict: true` et avec les outils du connecteur MCP de l'API, d'où son intérêt pour les outils que vous définissez vous-même. C'est le pendant, côté API, du Code Mode de Claude Code (section 4).

**Moins de serveurs.** Un serveur par projet plutôt que dix par habitude, et des descriptions courtes mais précises. Le serveur le moins cher reste celui qu'on n'a pas branché.

## 4. Définition de terminé

- Le coût des définitions est chiffré, en tokens, avec et sans `ESCALE_MCP_DIFFERE=1`.
- L'agent trouve encore `search_hotels` en mode différé (une question sur un hôtel à Lyon suffit).
- Chacun sait dire quel serveur de son équipe il passerait en `alwaysLoad`, et pourquoi.
