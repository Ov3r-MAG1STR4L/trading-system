# 003 — Backtest Python multi-paires (MT5)

**Date :** 2026-10-27
**Version :** `scripts/backtest.py` (v0.3, premier moteur)
**Données :** compte démo MetaQuotes, H4 depuis 2014, D1 depuis 1994
**Statut :** Rejetée (les deux stratégies)

## Hypothèse
Les stratégies 001 et 002 ont peut-être un avantage visible sur un échantillon plus large (5 paires, 2 unités de temps).

## Protocole
- Marchés : EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD — H4 et D1.
- Signal à la clôture, entrée à l'ouverture suivante (pas de look-ahead sur l'entrée).
- Stop et objectif touchés dans la même bougie → on compte le stop (hypothèse prudente).
- Spread historique du broker déduit. **Swaps, slippage et commissions absents.**
- Résultats en R, capitalisation composée à 1 % de risque.

## Résultats globaux
| Stratégie | Trades | % gagnants | Facteur de profit | Espérance |
|---|---|---|---|---|
| MA_cross_trend | 1 347 | 33,9 % | 1,006 | +0,004 R |
| RSI_mean_rev | 267 | 58,4 % | 1,041 | +0,017 R |

Détail par marché : `reports/2026-10-27_v0.3_multi-paires/results_summary.csv`.

Points notables :
- Résultats dispersés : MA_cross gagne sur GBPUSD H4 (+29,7 %) mais perd sur USDCAD H4 (−17,3 %, DD 32,9 %).
- RSI AUDUSD D1 : facteur de profit 1,98 mais sur **11 trades** seulement.
- Séries de pertes jusqu'à 13 d'affilée.
- EURUSD D1 et USDJPY D1 absents (historique insuffisant chez le broker démo).

## Conclusion
Espérance quasi nulle. Les swaps, le slippage et les commissions (non inclus) suffiraient à la rendre négative. Écart à zéro non significatif.

## Décision
**Rejetée.** Le moteur de backtest est conservé comme base de l'outil de recherche.
