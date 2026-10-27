# 002 — RSI retour à la moyenne (TradingView)

**Date :** 2026-10-27
**Outil :** TradingView, Strategy Tester
**Statut :** Rejetée

## Hypothèse
Après un excès (RSI < 30 ou > 70), le prix revient vers sa moyenne, dans le sens de la tendance de fond (EMA 200).

## Protocole
- Entrée : RSI(14) repasse au-dessus de 30 (achat, prix > EMA 200) ou sous 70 (vente, prix < EMA 200).
- Sortie : RSI revient à 50, ou stop 2 × ATR(14). Risque 1 %.

## Résultats
| Marché | UT | Période | Trades | % gagnants | Facteur de profit | Profit net |
|---|---|---|---|---|---|---|
| EURUSD | 1D | 1974-2026 | 41 | 43,9 % | 0,58 | −98,86 $ |
| EURUSD | 4H | 2023-2026 | 18 | 66,7 % | 1,22 | +13,11 $ |
| GBPUSD | 4H | 2023-2026 | 18 | 55,6 % | 0,79 | −17,01 $ |
| USDJPY | 4H | 2023-2026 | 18 | 61,1 % | 1,34 | +0,15 $ ⚠️ |
| AUDUSD | 4H | 2023-2026 | 10 | 40 % | 0,34 | −39,94 $ |

## Erreur découverte
⚠️ USDJPY faussé : la taille de position mélangeait dollars et yens (positions minuscules).
Correction : `qty = strategy.convert_to_symbol(strategy.equity * riskPct / 100) / stopDist`.
Leçon → raisonner en **R** plutôt qu'en devise (adopté pour la suite).

## Conclusion
Le bon résultat EUR/USD 4H (18 trades) ne se retrouve ni sur les autres paires ni sur longue période : hasard.

## Décision
**Rejetée.**
