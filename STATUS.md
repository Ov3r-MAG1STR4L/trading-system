# État du projet

**Dernière mise à jour :** 2026-10-27

## Étape actuelle

**0 — Environnement**

## Objectif actuel

Créer un environnement de recherche sécurisé et reproductible.

## Prochaine étape

Identifier les instruments disponibles (`scripts/lister_symboles.py`) et récupérer proprement les données historiques.

## Trading réel

**INTERDIT À CE STADE.**

Aucun script ne doit envoyer d'ordre, même sur le compte démo, avant l'étape « Paper trading » et la validation des règles de [`docs/regles-de-risque.md`](docs/regles-de-risque.md).

## Vérifications de l'environnement

| Élément | État | Comment vérifier |
|---|---|---|
| Python 3.13 | ✅ trouvé (`AppData\Local\Programs\Python\Python313`) | `python --version` |
| Paquets Python | ✅ numpy, pandas, MetaTrader5 | `python scripts/check_env.py` |
| Git | ✅ trouvé (`C:\Program Files\Git`) | `git --version` |
| GitHub CLI | ✅ trouvé | `gh --version` |
| MetaTrader 5 | ✅ installé, compte démo créé | `python scripts/check_env.py` |
| Python ↔ MT5 | ✅ check_env.py OK (démo) | `python scripts/check_env.py` |
| Dépôt GitHub | ⏳ à créer (privé) | `gh repo view` |

## Déjà fait (avant la structuration du projet)

- 3 expériences de backtest, toutes **rejetées** — voir [`docs/journal/`](docs/journal/).
