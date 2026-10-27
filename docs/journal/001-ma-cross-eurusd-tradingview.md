# 001 — Croisement de moyennes mobiles EUR/USD (TradingView)

**Date :** 2026-10-27
**Outil :** TradingView, Strategy Tester — `strategies/pine/croisement_mm_eurusd.pine`
**Statut :** Rejetée

## Hypothèse
Un croisement EMA 20 / EMA 50 capte les tendances sur EUR/USD.

## Protocole
- Stop = 2 × ATR(14), objectif = 2R, risque 1 % par trade, capital 1 000 $.
- Commission 0,002 %, slippage 2 ticks.
- Variantes testées successivement : sans filtre, avec filtre EMA 200, en 4H puis en 1D.

## Résultats
| Variante | Période | Trades | % gagnants | Facteur de profit | Profit net |
|---|---|---|---|---|---|
| 4H sans filtre | 2023-2026 | 93 | ~25 % | < 1 | ≈ −60 $ |
| 4H + filtre EMA 200 | 2023-2026 | 54 | 31,5 % | 0,85 | −40,50 $ |
| 1D + filtre EMA 200 | 1974-2026 | 173 | 33 % | 1,02 | +26,65 $ (DD 19,4 %) |

En 1D, la courbe monte jusqu'en 2002 puis redescend jusqu'à aujourd'hui.

## Problèmes rencontrés
- Aucun trade au départ : TradingView exige 100 % de marge par défaut → ajout de `margin_long=20`, `margin_short=20` (levier 1:5).
- Confusion entre le bouton de période « 1D » et l'unité de temps des bougies.

## Conclusion
Pas d'avantage exploitable. Le gain apparent en 1D est nul sur 52 ans et l'avantage semble avoir disparu depuis ~2002.

## Décision
**Rejetée.**
