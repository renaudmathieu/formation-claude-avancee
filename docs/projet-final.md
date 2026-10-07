# Doc42, projet final (section 11)

Checkpoint `etape/11-final`. Jalon : **variante métier livrée et présentée**.

Cette journée n'apporte aucune notion nouvelle : on part du Doc42 construit aux sections 1 à 10 et on l'adapte à un cas métier, en une journée (7 h), avec une contrainte qui structure tout : **ce qui est livré doit fonctionner**.

Ce document est le README du projet final. Il décrit les trois variantes, les critères d'évaluation, le contrat commun que toute variante doit satisfaire, puis comment lancer la variante de référence (B, analyseur de documents métier) depuis un dépôt propre.

## 1. Les trois variantes

Chacune part du Doc42 existant et en modifie deux ou trois briques. Choisissez celle dont vous pouvez fournir le corpus vous-même : un projet sur des données réelles apprend plus qu'un projet sur des données inventées.

| Variante | Ce qui change par rapport à Doc42 | La difficulté | Pour qui |
| --- | --- | --- | --- |
| **A. Assistant de support** | Le corpus devient une base de connaissances produit. Aiguillage vers `MODELE_RAPIDE` pour classer l'intention, outil de création de ticket. | L'escalade : savoir dire « je ne sais pas » et passer la main. | Produit, support, SaaS |
| **B. Analyseur de documents métier** | Le corpus devient vos vrais documents. Extraction structurée renforcée, comparaison entre documents. | La fiabilité de l'extraction, mesurée sur un jeu de test. | Juridique, finance, conseil |
| **C. Assistant de code interne** | Le corpus devient un dépôt de code et sa documentation, exposé en serveur MCP consommé depuis Claude Code. | Le découpage d'un corpus de code, qui ne se coupe pas comme de la prose. | Plateforme, outillage, DevEx |

Une quatrième option existe : proposer la vôtre au formateur, à condition qu'elle tienne en une journée et réutilise au moins quatre briques de Doc42.

### A. Assistant de support

- **Corpus** : une base de connaissances produit (FAQ, procédures, notes de version), un fichier Markdown par article, dans un dossier passé par `DOC42_CORPUS`.
- **Briques modifiées** : un premier appel à `MODELE_RAPIDE` classe l'intention (question produit, incident, demande commerciale, hors sujet) avant la boucle ; un outil `creer_ticket(titre, description, priorite)` remplace `creer_fiche`.
- **Déclaration** : `Variante(nom="support", outils=[chercher_documents, creer_ticket], irreversibles={"creer_ticket"})`. `creer_ticket` crée quelque chose chez un tiers : il passe par la confirmation humaine.
- **Escalade** : c'est le cœur de la variante. Une réponse sans source vérifiée passe la main (`raison="sans_source"`), et une intention « hors sujet » ou « incident » aussi, avant même d'appeler le modèle principal.
- **Jeu d'évaluation** : au moins dix questions, dont au moins trois où la bonne réponse est de passer la main. Le chiffre qui compte : le taux de « je ne sais pas » justifiés.
- **Coût** : la requête coûte deux appels (tri puis réponse) ; le journal les regroupe sous le même `requete_id`. Mesurez ce que le tri fait gagner, ou perdre.

### B. Analyseur de documents métier (variante de référence)

- **Corpus** : vos contrats, comptes rendus ou rapports, anonymisés (voir la section 4). À défaut, le corpus Hexalis du dépôt.
- **Briques modifiées** : un outil d'extraction forcé (`tool_choice`) rend des champs typés ; chaque valeur extraite est confrontée au texte source sans appel à l'API ; la comparaison de deux documents se fait sur leurs extractions, champ par champ ; un outil `lire_document` complète la recherche lexicale.
- **Déclaration** : `Variante(nom="analyseur", outils=[chercher_documents, lire_document, creer_fiche], irreversibles={"creer_fiche"})`.
- **Escalade** : sans source vérifiée, la réponse passe la main ; une valeur extraite introuvable dans le document est signalée à côté de l'extraction.
- **Jeu d'évaluation** : deux jeux. Des questions (`evals/analyseur_cas.jsonl`, 14 cas dont 2 d'escalade) et une référence d'extraction (`evals/analyseur_extraction.jsonl`, 11 documents, 37 champs).
- Elle est livrée complète dans `doc42/variantes/analyseur.py`, avec sa spécification : `docs/specification-analyseur.md`.

### C. Assistant de code interne

- **Corpus** : un dépôt de code et sa documentation. Pas de PDF, pas de prose : des fichiers source.
- **Briques modifiées** : le chargeur découpe le code par fonction ou par classe (le module `ast` pour Python) au lieu de le couper par paragraphes ; les outils deviennent `chercher_code(requete)` et `lire_fichier(chemin)` ; le tout est exposé par le serveur MCP de la section 6 et consommé depuis Claude Code.
- **Déclaration** : `Variante(nom="code", outils=[chercher_code, lire_fichier], irreversibles=frozenset())`. En lecture seule, aucune confirmation n'est nécessaire, et `verifier_variante` le confirme : c'est un argument à défendre en présentation.
- **Escalade** : une réponse qui ne cite aucun fichier renvoyé par les outils passe la main ; les sources sont des chemins (`[doc42/outils.py]`), la convention entre crochets reste la même.
- **Jeu d'évaluation** : au moins dix questions du type « où est définie X », « qui appelle Y », avec le fichier attendu en source.
- **Dépendance** : le paquet `mcp`, déjà requis à la section 6.

## 2. Les critères d'évaluation

### La spécification d'une page, avant de coder

Quatre questions, quatre réponses courtes, relues à 0 h 30 par un pair puis par le formateur :

1. **Quoi** : la fonctionnalité en trois phrases, avec un exemple d'entrée et un exemple de sortie attendue.
2. **Comment on saura que ça marche** : le critère de réussite, chiffré. « Huit questions sur dix reçoivent une réponse correctement sourcée » vaut mieux que « ça répond bien ».
3. **Ce qui est hors périmètre** : au moins trois choses que vous ne ferez pas aujourd'hui.
4. **Le risque principal** : ce qui, si ça se passe mal, vous fera perdre deux heures.

### Attendu, et pas attendu

**Attendu** : une application qui tourne, un jeu d'évaluation même minimal, des garde-fous explicites, des logs qui permettent de dire ce que ça coûte, un README qu'un collègue peut suivre.

**Pas attendu** : une interface utilisateur soignée, un déploiement en production, une couverture de tests exhaustive, des performances optimisées.

Un périmètre réduit qui fonctionne vaut mieux qu'un périmètre ambitieux qui plante à la démonstration.

### Définition de terminé

- [ ] La spécification d'une page existe et a été relue avant le début du code.
- [ ] L'application se lance depuis un dépôt propre en suivant le README, sans intervention de l'auteur.
- [ ] Un jeu d'évaluation, même de dix cas, donne un chiffre de réussite.
- [ ] Les garde-fous sont explicites : bornes, confirmation humaine sur les actions irréversibles, gestion des erreurs.
- [ ] Les logs permettent de dire ce que coûte une requête.
- [ ] La démonstration de dix minutes a eu lieu et l'auteur a répondu à au moins une question sur ses choix.
- [ ] Le checkpoint `etape/11-final` est commité.

### La présentation (dix minutes)

La spécification, une démonstration du chemin nominal, une escalade (une question hors corpus), le chiffre d'évaluation et le coût par requête lus dans le journal, puis les questions. Prévoyez une capture de secours : une démonstration qui plante est un résultat, à condition de savoir dire pourquoi.

## 3. Le contrat commun

Toute variante, quelle qu'elle soit, s'appuie sur `doc42/variantes/socle.py`, qui est le corrigé de `tests/test_section11.py`. Les tests (`uv run pytest tests/test_section11.py`) rendent la définition de terminé vérifiable hors ligne :

| Critère de la page | Ce que le socle garantit | Exercice |
| --- | --- | --- |
| Spécification relue | `verifier_specification` : quatre sections, exemple d'entrée et de sortie, critère chiffré, trois éléments hors périmètre | 1 |
| Données réelles | `anonymiser` : e-mails, téléphones, IBAN masqués avant tout envoi | 2 |
| Garde-fous explicites | `verifier_variante` : outils décrits, modèle tarifé, pas de garde-fou fantôme, pas d'outil d'écriture non déclaré | 3 |
| Coût d'une requête | `cout_appel` et `Journal` : une ligne JSON par appel, coût agrégé par `requete_id` | 4 |
| Confirmation humaine, erreurs | `resultat_outil` : refus par défaut des actions irréversibles, erreurs d'outil rendues au modèle | 5 |
| Bornes | `repondre` : taille de question, nombre de tours, budget, erreurs de l'API, sources vérifiées, escalade | 6 |
| Un chiffre de réussite | `charger_cas` et `evaluer` : au moins dix cas, un taux, les échecs et leur raison, le coût | 7 |
| Dépôt propre, README suivable | `verifier_livrable` : README, `.gitignore`, spécification, jeu d'évaluation | 8 |

Le socle ne dépend ni de `doc42.agent` (section 8), ni de `doc42.rag` (section 9), ni de `doc42.observabilite` et `doc42.garde_fous` (section 10) : il porte sa propre boucle bornée et son propre journal, pour qu'une variante se lance même si l'un de ces checkpoints est incomplet. Brancher la recherche hybride de la section 9 à la place de `chercher_documents`, ou le journal de la section 10 à la place de `Journal`, est la première amélioration à proposer après la journée.

## 4. Lancer la variante de référence

Depuis un clone propre du dépôt, au checkpoint `etape/11-final` :

```bash
uv sync
cp .env.example .env        # puis renseignez ANTHROPIC_API_KEY dans .env
uv run python -m doc42.variantes.analyseur verifier
```

`verifier` tourne hors ligne et sans clé : il contrôle la déclaration de la variante et le livrable (ce README, la spécification, le jeu d'évaluation, le `.gitignore`). Il doit afficher « Livrable conforme au contrat de la section 11 ».

Les commandes suivantes appellent l'API et demandent la clé :

```bash
# Une question, avec sources vérifiées, coût et requête journalisés
uv run python -m doc42.variantes.analyseur demander "Quelles sont les échéances du contrat Alpha ?"

# Une question hors corpus : la variante passe la main
uv run python -m doc42.variantes.analyseur demander "Quel était le chiffre d'affaires de Beta Santé en 2025 ?"

# Une action irréversible : creer_fiche demande confirmation dans le terminal ([o/N])
uv run python -m doc42.variantes.analyseur demander "Crée une fiche de synthèse du contrat Beta Santé"

# Extraction structurée, avec les valeurs introuvables dans le document signalées
uv run python -m doc42.variantes.analyseur extraire contrat_alpha

# Comparaison champ par champ de deux documents
uv run python -m doc42.variantes.analyseur comparer contrat_alpha avenant_alpha_01

# Le chiffre : questions puis extraction, avec le coût total
uv run python -m doc42.variantes.analyseur evaluer
uv run python -m doc42.variantes.analyseur evaluer --sans-extraction
```

Où sont les choses :

- **Corpus** : `corpus/` par défaut, un autre dossier avec `DOC42_CORPUS=/chemin`. Les documents partent vers l'API après `anonymiser` ; les noms propres ne sont pas masqués, relisez votre corpus avant.
- **Fiches** : `fiches/` (ou `DOC42_FICHES`), ignoré par git. Une évaluation n'écrit jamais de fiche : la confirmation y est toujours refusée.
- **Journal des coûts** : `fiches/journal-analyseur.jsonl` (ou `DOC42_JOURNAL`), une ligne JSON par appel avec `requete`, `modele`, tokens d'entrée, de sortie et de cache, et `cout` en dollars. Le coût d'une question est la somme des lignes de son `requete_id`, affiché à la fin de chaque commande.
- **Bornes** : 6 tours, 2 000 caractères de question, 0,10 $ par requête (`Bornes` dans le socle), 6 000 caractères par lecture de document.
- **Modèle** : `MODELE_DEFAUT` de `doc42/config.py`, pour la réponse comme pour l'extraction. Aucun identifiant de modèle ailleurs.

## 5. Pièges de la journée

- **Le périmètre trop large** est le seul vrai risque : il se manifeste par rien à montrer à 6 h. La revue de 0 h 30 existe pour le couper.
- **Un corpus non préparé mange deux heures.** Vérifiez avant la formation que vos documents sont lisibles et qu'aucune donnée personnelle ne s'y trouve.
- **Les données réelles** peuvent être confidentielles. Vérifiez ce que votre politique interne autorise avant d'envoyer quoi que ce soit à une API, et anonymisez.
- **Déléguer trop à l'agent** produit du code que vous ne saurez pas défendre. Ce que vous ne pouvez pas expliquer, réécrivez-le.
- **Ce projet n'est pas prêt pour la production.** Il lui manque au minimum ce que la section 10 liste : gestion des secrets, quotas, alertes, plan de reprise.
