# 001 — Donchian breakout (baseline)

**Date :** 2026-10-28 (écrit AVANT tout résultat)
**Version Git :** après v0.3 (commit noté dans `experience.json` au lancement)
**Statut :** En cours

## Hypothèse
Un breakout de Donchian, la forme la plus simple de suivi de tendance, peut avoir une espérance positive après coûts
lorsqu'il est appliqué de la même façon à un portefeuille diversifié (forex, indices, métaux). L'avantage attendu vient de
la diversification et des rares grandes tendances, pas d'un signal fin. Taux de réussite attendu faible (30-40 %).
C'est une **baseline** pour tester le laboratoire ; un échec est un résultat acceptable.

## Protocole (docs/protocole-recherche-v0.4.md, figé)
- Marchés : les 12 de `config/marches.csv`, D1, mêmes règles partout.
- Entraînement : 2012-08-06 → 2019-12-31 ; validation : 2020-01-01 → 2022-12-31 ;
  OOS : 2023-01-01 → 2026-10-27 (une seule ouverture, seulement pour une variante KEEP).
- Règles : long si clôture > plus haut des N bougies précédentes, short si < plus bas ; stop = k × ATR(20) ;
  sortie si clôture franchit le canal opposé de N/2 bougies ; pas d'objectif ; signal à la clôture, exécution à
  l'ouverture suivante.
- Grille fixée : N ∈ {20, 55, 100} × k ∈ {2, 3} = **6 variantes**, aucune autre.
- Risque : 0,25 % du capital réalisé par trade, sans plafond, exposition mesurée.
- Coûts : spread = max(spread de la bougie, médiane des spreads > 0 sur 2012-2022) ; slippage 0 (base) et
  1 × plancher par exécution (stress) ; swaps actuels appliqués à l'historique (approximation).
- Benchmark : 200 tirages d'entrées aléatoires sur la validation (mêmes marchés, même nombre de signaux par marché,
  mêmes stops et sorties). Décision sur R après spread/slippage.
- Critères : section 5 du protocole (rejet si un seul critère échoue).

## Biais vérifiés
- [x] Look-ahead : tests `test_donchian_sans_lookahead`, données tronquées à la fin de chaque période
- [x] Surapprentissage : 6 variantes, fixées avant le test, compteur global dans `experiments/registre_variantes.csv`
- [x] Coûts : spread, slippage de stress, swaps
- [ ] Taille d'échantillon / stabilité : jugées par les critères, voir `decision.json`

## Conclusion
(à remplir après les résultats, sans modifier ce qui précède)
