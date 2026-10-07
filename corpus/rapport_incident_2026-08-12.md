# Rapport d'incident du 12 août 2026

Type : rapport d'incident
Date : 14 août 2026
Gravité : majeure
Auteur : équipe d'astreinte

## Chronologie
- 09:42 : hausse des erreurs 5xx sur l'API de recherche.
- 09:55 : astreinte prévenue par l'alerte de disponibilité.
- 10:20 : cause identifiée, un index corrompu après une mise à jour du moteur de recherche.
- 11:05 : retour à la normale après reconstruction de l'index.

## Impact
Recherche indisponible pendant 1 heure 23 minutes pour l'ensemble des clients. Aucune perte de données.

## Actions
- Ajouter un contrôle d'intégrité de l'index avant la bascule. Responsable : Nadia Benali, échéance 30 septembre 2026.
- Documenter la procédure de reconstruction. Responsable : équipe d'astreinte, échéance 15 septembre 2026.
