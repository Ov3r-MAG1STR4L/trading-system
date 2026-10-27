# État du projet

**Dernière mise à jour :** 2026-10-28

## Étape actuelle

**v0.2 — Données** (v0.1 terminée, tag `v0.1`)

## Objectif actuel

Obtenir un jeu de données historique D1 fiable et contrôlé pour les 12 marchés retenus.

## Prochaine étape

Données D1 téléchargées et contrôlées (rapport `reports/2026-10-28_v0.2_donnees/`). Décider du traitement des anomalies, puis récupérer les swaps. Pas de stratégie avant validation.

## Univers de marchés (v0.2)

12 marchés, listés dans [`config/marches.csv`](config/marches.csv) :

- **Forex (7)** : EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD
- **Indices (3)** : US500, US30, DE40
- **Métaux (2)** : XAUUSD, XAGUSD

Critères (inventaire du 2026-10-28, 36 symboles disponibles chez MetaQuotes-Demo) :
1. Historique D1 depuis 2012 ou avant → période commune d'environ 13 ans, ce qui laisse de la place pour une période hors échantillon.
2. Des marchés de familles différentes (forex, indices, métaux) : la diversification est la source de l'avantage visé.
3. Exclus : les croisements forex (combinaisons des majeures), les symboles qui démarrent en 2019 ou après (FRA40, UK100, USTEC, COPPER…) et les variantes « M » (doublons en mini-taille).

Limites connues : pas d'énergie chez ce broker ; US30 et US500 sont très corrélés ; le forex d'avant 2000 est peut-être reconstruit.
Sélection figée : on ne l'optimise pas (risque de surapprentissage par le choix des marchés).

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
