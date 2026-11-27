# Python express

Cinq minutes pour lire `escale/chat.py` sans avoir jamais fait de Python. Cette page ne couvre que ce qui sert au TP 1.

## Les commandes

| Commande | Ce qu'elle fait | Équivalent Maven |
| --- | --- | --- |
| `uv sync` | Installe les dépendances du projet | `mvn dependency:resolve` |
| `uv run pytest -q` | Lance les tests | `mvn test` |
| `uv run ruff check .` | Vérifie le style du code | `mvn checkstyle:check` |
| `uv run python -m escale chat` | Lance le programme | `mvn exec:java` |

Il n'y a rien à compiler ni d'environnement à activer : `uv run` s'en charge. Python n'a pas besoin d'être installé à l'avance : `uv sync` télécharge la bonne version si besoin.

## Lire le code

| Python | Ce que ça veut dire | Équivalent Java |
| --- | --- | --- |
| Un bloc décalé de 4 espaces | L'indentation délimite les blocs : elle est obligatoire | `{ ... }` |
| `# texte` | Un commentaire | `// texte` |
| `def ask(self, text):` | Une méthode, pas de point-virgule en fin de ligne | `String ask(String text) {` |
| `def __init__(self, client):` | Le constructeur | `Conversation(Client client) {` |
| `self.messages` | Un attribut de l'objet courant, `self` est toujours écrit | `this.messages` |
| `messages = []` | Une liste vide, sans déclarer de type | `new ArrayList<>()` |
| `messages.append(x)` | Ajoute à la fin de la liste | `messages.add(x)` |
| `messages.pop()` | Retire le dernier élément | `messages.remove(messages.size() - 1)` |
| `{"role": "user"}` | Un dictionnaire modifiable : des clés et des valeurs | Une `HashMap` déjà remplie |
| `None` | L'absence de valeur | `null` |
| `send(a, b, system=c)` | `a` et `b` sont passés dans l'ordre, `system` est un argument nommé | Pas d'équivalent direct pour le nom |
| `text: str`, `-> str`, `list[dict]` | Le type attendu, une indication que Python ne vérifie pas à l'exécution | `String text` |
| `str \| None` | Une chaîne ou rien | Une `String` qui peut être `null` |
| `try:` / `except Erreur:` | Attrape une erreur | `try { } catch (Erreur e) { }` |
| `except (A, B):` | Attrape l'une ou l'autre | `catch (A \| B e)` |
| `raise` seul | Relance l'erreur en cours | `throw e;` |
| `f"Erreur : {error}"` | Du texte avec une valeur insérée | `"Erreur : " + error` |

## Remplir un trou

Le travail se fait dans `escale/chat.py`, méthode `Conversation.ask`. Avant de commencer, supprimez la ligne `pytestmark = ...` en haut de `tests/test_chat.py` : tant qu'elle est là, ces tests sont ignorés. C'est la seule modification de test à faire.

`hole("...")` est une petite fonction qui arrête le programme et affiche ce qu'il reste à écrire. Pour remplir un trou, remplacez tout l'appel `hole(...)`, parenthèses comprises, par la bonne valeur. Le reste de la ligne ne change pas.

```python
# Avant
print(hole("le prénom à afficher"))

# Après
print(prenom)
```

Le trou 1 ne demande que trois valeurs, de la forme `nom` ou `objet.attribut`, sans appel de fonction. Pour le 1.3, regardez comment `text_of` lit `response` dans `escale/llm.py` : il faut garder tous les blocs, pas seulement le texte.

## Lire le résultat des tests

Pour une sortie courte, avec une ligne par échec :

```bash
uv run pytest -q --tb=line
```

Commencez par la dernière ligne, qui donne le bilan :

```txt
8 failed, 3 passed, 1 skipped
```

Des tests rouges au début du TP sont normaux : ils forment la liste de ce qu'il reste à faire. Le message `TP 1, à compléter : trou 1.1` nomme le trou à remplir. Ne modifiez pas le contenu des tests pour les faire passer.

## Trois erreurs fréquentes

| Message ou symptôme | Cause probable |
| --- | --- |
| `IndentationError` | Une ligne n'est pas décalée comme ses voisines |
| `SyntaxError` | Une parenthèse, un guillemet ou une virgule a été effacé avec le `hole(...)` |
| `NameError: name 'messages' is not defined` | Il manque `self.` devant `messages` |
