# Journal des décisions

Format : date — décision — raison.

- **2026-10-27** — Pas de trading réel tant que la progression complète (validation hors échantillon + paper trading) n'est pas faite. — Débutant, capital limité, aucune stratégie validée.
- **2026-10-27** — Résultats exprimés en **R** (multiples du risque) plutôt qu'en devise. — Évite les erreurs de conversion (bug observé sur USDJPY dans TradingView) et rend les marchés comparables.
- **2026-10-27** — Données MT5 (compte démo MetaQuotes) plutôt que TradingView pour la recherche. — Export gratuit, automatisable, spread historique disponible.
- **2026-10-27** — Abandon des stratégies « classiques » MA cross et RSI retour à la moyenne sur forex seul. — Facteur de profit ≈ 1 sur 1 614 trades (voir journal 001 à 003).
- **2026-10-27** — Prochaine piste : suivi de tendance **diversifié** multi-marchés. — Seule famille de stratégies simples avec un historique documenté sur longue période ; l'avantage vient de la diversification, pas du signal.
- **2026-10-27** — Dépôt GitHub **privé**. — Pourra devenir public plus tard pour du contenu pédagogique.
- **2026-10-28** — Univers de départ figé à 12 marchés (7 forex, 3 indices, 2 métaux), voir `STATUS.md`. — Historique ≥ 2012 et diversification ; pas d'optimisation de la sélection.
- **2026-10-28** — Période de référence des backtests de portefeuille : **2012-08-06 → aujourd'hui**. Les données plus anciennes restent dans `data/` sans être utilisées. — Période commune aux 12 marchés ; le forex d'avant 2012 est reconstruit (bougies plates).
- **2026-10-28** — Aucune donnée n'est modifiée : pas d'interpolation des trous, pas de correction des bougies plates, pas de suppression des rendements extrêmes (CHF 2015, Brexit, Covid, XAGUSD 2026). — Ne jamais modifier une donnée pour embellir un backtest.
- **2026-10-28** — Les trous du broker (indices, été 2025) seront traités par le moteur v0.3 comme `DATA_GAP / NON_TRADABLE`, tests à l'appui. — Un trou n'est ni un prix inchangé ni un rendement nul.
- **2026-10-28** — Swaps : on utilise les valeurs actuelles du broker, faute d'historique, en le signalant comme limitation. — Mieux vaut un coût approximatif qu'aucun coût.
- **2026-10-28** — **v0.2 Données : TERMINÉE**, avec les limitations listées dans `STATUS.md`.
