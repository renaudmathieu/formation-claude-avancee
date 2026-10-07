# Spécification : Doc42, variante B, analyseur de documents métier

Une page, écrite avant le code et relue à 0 h 30. Format vérifié par `verifier_specification` (section 11, exercice 1).

## Quoi

Doc42 répond aux questions sur les documents internes d'Hexalis (contrats, avenants, factures, comptes rendus) en citant ses sources vérifiées, extrait de chaque document des champs typés (type, date, échéances, montant HT) et compare deux documents champ par champ. Une valeur extraite introuvable dans le texte source est signalée. Une question sans réponse dans le corpus est transmise à un humain.

Entrée : `comparer contrat_alpha avenant_alpha_01`

Sortie attendue :

```
type : contrat -> avenant
date : 02/11/2026 -> 18/12/2026
montant_total_ht : 48000.0 -> 54000.0
```

Entrée : « Quelles sont les échéances de paiement du contrat Alpha Logistique ? »

Sortie attendue : « 15/01/2027, 15/04/2027 et 15/07/2027 [contrat_alpha] »

## Critère de réussite

- Au moins 11 questions sur 14 du jeu `evals/analyseur_cas.jsonl` réussies, dont les 2 cas où il faut passer la main.
- Au moins 90 % des champs corrects sur le jeu de référence `evals/analyseur_extraction.jsonl` (11 documents, 37 champs).
- Coût moyen d'une question inférieur à 0,05 $, lu dans le journal.

## Hors périmètre

- Les PDF scannés et l'OCR : le corpus est en Markdown.
- L'interface graphique : la ligne de commande suffit pour la démonstration.
- La recherche hybride de la section 9 : la recherche lexicale de `doc42.outils` reste en place.
- Le déploiement et les quotas par utilisateur (section 10).
- L'extraction de clauses libres (pénalités, résiliation) : seuls quatre champs typés sont extraits.

## Risque principal

Les champs ambigus. L'avenant mentionne trois échéances dont deux « inchangées », le rapport d'incident porte deux dates (l'incident et la rédaction). Si la référence et le schéma ne tranchent pas ces cas, le taux d'extraction mesure le désaccord entre deux lectures, pas la fiabilité. Parade : les descriptions du schéma disent quelle lecture retenir, et la référence est relue par un pair avant la première mesure.
