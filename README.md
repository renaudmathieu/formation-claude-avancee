# Escale

Assistant de déplacement professionnel, construit pas à pas avec Claude Code pendant la formation « Maîtrisez l'écosystème Anthropic de bout en bout ».

Ceci est le point de départ. L'appel à l'API, la ligne de commande et les tests sont fournis : il reste à compléter `escale/chat.py` pendant la section 2 (ses trous sont marqués `TP 1` dans le code).

**Jamais fait de Python ?** Commencez par [le rappel Python](docs/python-express.md), 5 minutes suffisent.

## Installation

Il faut seulement [`uv`](https://docs.astral.sh/uv/getting-started/installation/) : il télécharge lui-même Python si besoin.

```bash
uv sync
cp .env.example .env   # puis renseigner les clés données par le formateur
```

Sous Windows PowerShell ou en invite de commandes, `cp` peut être remplacé par `copy`.

## Vérifier que tout marche

```bash
uv run pytest -q
```

Résultat attendu : `10 passed, 9 skipped`. Les tests n'appellent ni l'API ni le réseau, ils passent sans clé. Les tests ignorés seront activés pendant la formation.

## Essayer

```bash
uv run python -m escale ask "Que mettre dans sa valise pour Lyon en novembre ?"
```

Il faut une clé dans `.env`, et chaque appel consomme du crédit API.

`uv run python -m escale chat` s'arrête sur le message `TP 1, à compléter` tant que `escale/chat.py` n'est pas rempli : c'est normal.

## Contenu du projet

| Chemin | Rôle |
| --- | --- |
| `escale/chat.py` | La conversation : le fichier à compléter |
| `escale/llm.py` | L'appel à l'API de Claude |
| `escale/__main__.py` | La ligne de commande |
| `escale/tools/weather.py` | La météo, via Open-Meteo |
| `tests/` | Les tests du projet |
| `docs/python-express.md` | Le rappel Python |
| `data/politique-voyage/` | La politique de voyage d'une entreprise fictive |
| `data/justificatifs/` | Dix justificatifs de dépenses fictifs |
| `exemples/billet-fictif.png` | Un billet de train fictif |
| `sortie/` | Les fichiers générés par Escale |

## En cas de panne

Si le service météo ne répond pas, ajouter `ESCALE_METEO=simule` dans `.env`.
