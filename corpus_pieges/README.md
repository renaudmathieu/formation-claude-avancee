# Documents piégés

Ces documents servent aux ateliers sur l'injection indirecte (section 6, étape 7, et section 8, étape 6). Ils ne font **pas** partie du corpus par défaut, et on ne les copie jamais dans `corpus/` : on prépare un corpus temporaire et on le désigne par la variable `DOC42_CORPUS`.

```bash
mkdir -p /tmp/corpus-piege && cp corpus/*.md corpus_pieges/note_fournisseur_piegee.md /tmp/corpus-piege/
DOC42_CORPUS=/tmp/corpus-piege uv run python -m doc42.agent "Quel est le nouveau délai de paiement de DataPlus ?"
```

Les tests font de même avec un dossier temporaire.
