# État du projet

**Dernière mise à jour :** 2026-10-28

## Étape actuelle

**v0.4 — RECHERCHE** (tag `v0.3` créé et poussé)

## Objectif actuel

v0.4 en cours, protocole **v0.4.1**, 276 tests.

| Expérience | Protocole | Variantes | Décision | OOS |
|---|---|---|---|---|
| 001 Donchian baseline | v0.4 (historique) | 6 | 6/6 REJECT | non ouvert |
| **002 momentum série temporelle** (dernière terminée) | v0.4.1 | 6 | 6/6 REJECT, `VALIDATION_COMPLETE — OOS_LOCKED` | non ouvert |

- Variantes testées au total : **12** (`experiments/registre_variantes.csv`). Aucune stratégie retenue.
- **OOS 2023-01-01 → 2026-10-27 : vierge.**
- Revue de 002 : [`docs/revue-experience-002.md`](docs/revue-experience-002.md). Aucune des six variantes ne démontre un
  avantage suffisamment robuste selon le protocole v0.4.1 (ce n'est pas une preuve que le momentum ne marche pas).
- 001 et 002 sont **historiques et immuables** (leurs scripts refusent de les rejouer).
- **Expérience 003 : aucune préparation ni exécution** avant décision sur les constats de la revue (benchmark).

## Prochaine étape

Audit v0.3 : [`docs/audit-v0.3.md`](docs/audit-v0.3.md). Lancer : `python -m pytest` puis `python scripts/backtest.py` (hors ligne, sans MT5).
Rapport v0.2 : [`reports/2026-10-28_v0.2_donnees/RAPPORT.md`](reports/2026-10-28_v0.2_donnees/RAPPORT.md).

## Données (v0.2)

- Période de référence des backtests : **2012-08-06 → aujourd'hui**. Les données plus anciennes restent dans `data/`, pour référence uniquement.
- Re-télécharger : `python scripts/telecharger_donnees.py` (contrôles inclus), puis `python scripts/recuperer_swaps.py`.
- Principe : **aucune donnée n'est modifiée, interpolée ni supprimée** pour améliorer un backtest.

### Limitations restantes
1. Trou du broker sur les indices : US500 et US30 du 2025-07-16 au 2025-09-09, DE40 du 2025-07-23 au 2025-09-09. À traiter en v0.3 comme `DATA_GAP / NON_TRADABLE`.
2. Forex d'avant 2012 reconstruit (bougies plates), donc exclu des backtests de référence.
3. Swaps : seulement les valeurs actuelles (2026-10-28), sans historique. Leur application au passé est approximative.
4. Krach XAGUSD de janvier-février 2026 (-31 % puis -22 % en un jour) : à vérifier avec une source indépendante.
5. Une seule source de données (broker démo MetaQuotes), sans comparaison avec une autre source.
6. Spread historique : la colonne `spread` des D1 donne la valeur du broker par bougie ; sa fiabilité n'est pas vérifiée.
7. Pas d'énergie dans l'univers ; US30 et US500 sont très corrélés.
8. Heure serveur MT5 non convertie (bougies D1 du broker).

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
