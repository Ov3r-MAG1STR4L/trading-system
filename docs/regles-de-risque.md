# Règles de risque

Principe fondamental :

> Ne jamais risquer une perte qui pourrait compromettre durablement le projet ou mes économies.

Ces règles sont fixées **avant** toute automatisation. Elles ne se modifient pas pour « se refaire » après une perte.
Toute modification doit être écrite dans [`decisions.md`](decisions.md) avec sa justification, à froid.

## Règles par trade

| Règle | Valeur | Statut |
|---|---|---|
| Risque maximal par trade | 1 % du capital | appliqué dans les backtests |
| Stop-loss | obligatoire, posé à l'entrée | appliqué dans les backtests |
| Levier effectif maximal | 1:5 | à appliquer en exécution |

## Règles de portefeuille

| Règle | Valeur proposée | Statut |
|---|---|---|
| Perte quotidienne maximale | 2 % → arrêt jusqu'au lendemain | à implémenter |
| Drawdown maximal | 10 % → arrêt complet + revue manuelle | à implémenter |
| Positions ouvertes simultanées | 5 maximum | à implémenter |
| Risque total ouvert | 3 % du capital maximum | à implémenter |

## Interdictions absolues

- Martingale ou toute augmentation de taille après une perte.
- Moyenne à la baisse (ajouter à une position perdante).
- Supprimer ou élargir un stop après l'entrée.
- Trader un compte réel sans validation hors échantillon **et** période de paper trading.
- Laisser l'IA décider seule de passer en réel.

## Coûts à intégrer dans chaque test

| Coût | Statut dans `backtest.py` v0.3 |
|---|---|
| Spread | ✅ inclus (spread historique du broker) |
| Slippage | ❌ absent |
| Swaps (frais overnight) | ❌ absent |
| Commissions | ❌ absent (compte démo MetaQuotes sans commission) |

## Arrêt d'urgence (à concevoir avant toute automatisation)

- Un interrupteur unique qui ferme les positions et coupe le script.
- Arrêt automatique si : perte du jour > limite, drawdown > limite, perte de connexion, données incohérentes, ordre rejeté de façon répétée.
