# Projet final

La dernière journée n'est pas un cours : vous construisez votre propre projet, avec ce que vous avez vu sur Escale. Le fil est le même que pour Escale : une spécification d'une page, un harnais (tests, évaluations, gardes) **avant** les fonctionnalités, puis des petits pas vérifiés.

Les neuf checkpoints `etape/02` à `etape/10` sont votre boîte à outils. Copiez ce qui sert, ne recopiez pas ce qui ne sert pas.

## Les trois variantes

Choisissez-en une. Chacune a un risque différent, c'est ce qui la rend intéressante.

### A. Assistant de support

Un assistant qui répond aux questions de clients ou de collègues à partir d'une base de connaissances (FAQ, procédures, pages d'aide), et passe la main à un humain quand il ne sait pas.

- **Ce que vous reprenez** : la recherche hybride et les citations vérifiées (section 9), le refus explicite hors corpus, le client robuste (section 2), le coût par question (section 10).
- **Le risque typique** : une réponse inventée, dite avec aplomb. Le harnais doit mesurer le taux de citations fausses et le taux de refus à bon escient.

### B. Analyseur de documents

Un outil qui lit des documents métier (factures, contrats, comptes rendus), en extrait des champs structurés et signale ce qui est douteux ou manquant.

- **Ce que vous reprenez** : l'extraction en sortie structurée, les versions de prompt et le jeu d'évaluation (section 3), la lecture d'images et de PDF (section 2), la règle « une information manquante est déclarée manquante ».
- **Le risque typique** : une valeur plausible mais fausse, qui part dans un système en aval. Le harnais doit comparer à un attendu écrit à la main, champ par champ.

### C. Assistant de code interne

Un agent qui lit un dépôt interne, répond aux questions des développeurs et propose des changements, jamais appliqués sans accord.

- **Ce que vous reprenez** : la boucle d'agent bornée en tours et en dollars, la confirmation avant toute action irréversible, les données externes traitées comme des données (section 8), `CLAUDE.md`, le hook de tests verts et un mod de garde (sections 5 et 7).
- **Le risque typique** : une instruction cachée dans un fichier lu par l'agent, ou une écriture hors du périmètre prévu. Le harnais doit contenir un fichier piégé et un test qui prouve que rien ne part sans confirmation.

## La spécification d'une page

Une page, pas plus. Si elle ne tient pas sur une page, le projet est trop gros pour la journée.

```markdown
# Nom du projet

## Quoi
Une ou deux phrases : pour qui, pour faire quoi. Un exemple concret d'entrée et de sortie.

## Comment on saura
Les mesures qui disent que ça marche : un jeu de dix à vingt cas écrits à la main, un seuil
(par exemple « au moins 90 % de réponses correctes, zéro citation inventée »), un budget par
question en dollars.

## Hors périmètre
Ce que vous ne ferez pas aujourd'hui, écrit noir sur blanc. Une interface graphique, un
déploiement et une base de données y figurent presque toujours.

## Le risque principal
Le pire qui puisse arriver, en une phrase, et la parade prévue. Si le pire est irréversible
(un envoi, une réservation, une écriture), la parade est une confirmation humaine.

## Le harnais
Ce qui est en place avant la première fonctionnalité : les tests (sans réseau, avec un faux client),
le jeu d'évaluation, les bornes de l'agent (tours, budget), le journal des appels.
```

Exemple rempli pour Escale, en miniature :

> **Quoi** : vérifier une note de frais contre la politique de voyage et dire, ligne par ligne, conforme ou non, avec la page citée.
> **Comment on saura** : dix justificatifs écrits à la main avec leur verdict attendu, 100 % de verdicts corrects, moins de 0,02 $ par note.
> **Hors périmètre** : le remboursement lui-même, les devises, l'interface.
> **Le risque principal** : un plafond lu de travers qui fait refuser une dépense légitime. Parade : le plafond est lu dans la politique, jamais dans le code, et un cas ambigu est déclaré « à vérifier ».
> **Le harnais** : `tests/test_check.py`, `evals/attendu.json`, le journal `.escale/trace.jsonl`.

## Le déroulé de la journée

Indicatif : le formateur ajuste selon le rythme du groupe.

| Horaire | Étape |
| --- | --- |
| 09:00 | Choix de la variante, rédaction de la spécification d'une page |
| 09:45 | Relecture croisée des spécifications en binômes : le risque principal est-il le bon ? |
| 10:15 | Le harnais d'abord : faux client, premiers tests, jeu d'évaluation, bornes de l'agent |
| 12:30 | Déjeuner |
| 13:30 | Les fonctionnalités, une par une, chacune avec son test, un commit à chaque pas vert |
| 15:30 | Mesurer : taux de réussite sur le jeu, coût par question, une optimisation de coût |
| 16:15 | Démonstrations de cinq minutes : la spécification, le chiffre, le risque et sa parade |
| 17:00 | Rétrospective et suite |

## Attendu, pas attendu

**Attendu**

- Une spécification d'une page, relue par un binôme.
- Un harnais en place avant les fonctionnalités : des tests qui n'appellent ni l'API ni le réseau, et un jeu d'évaluation écrit à la main.
- Une garde sur toute action irréversible, avec son test.
- Un coût mesuré par question, et un budget.
- Des données fictives ou publiques : jamais de vraies données clients dans le dépôt.
- Un dépôt propre : `uv run pytest -q` et `uv run ruff check .` verts, aucune clé dans un fichier suivi.

**Pas attendu**

- Une interface graphique ou un déploiement.
- Une base de données vectorielle ou un framework d'agents : la recherche par mots-clés, ou un tableau de vecteurs, suffit.
- Plusieurs agents qui se parlent.
- Un projet « fini » : un projet mesuré et borné vaut mieux qu'un projet large et invérifiable.

## Terminé, c'est quand

Vous pouvez dire, chiffres à l'appui, **ce que fait le projet, ce qu'il ne fait pas, ce qu'il coûte, et ce qui l'empêche de faire une bêtise irréversible.**
