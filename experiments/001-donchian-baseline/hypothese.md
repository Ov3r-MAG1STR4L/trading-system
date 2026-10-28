# 001 — Donchian breakout (baseline)

**Date :** 2026-10-28 (écrit AVANT tout résultat)
**Version Git :** après v0.3 (commit noté dans `experience.json` au lancement)
**Statut :** Rejetée (6/6 variantes REJECT, OOS non ouvert)

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
Ajoutée le 2026-10-28 après les résultats (commit de lancement : `94be67c`). Détail : `resultats.csv`, `decision.json`.

| Variante | Entr. trades | Entr. E (R) | Valid. trades | Valid. E (R) | Stress valid. | Benchmark valid. médiane / 95e |
|---|---|---|---|---|---|---|
| N20_S2 | 759 | -0,048 | 306 | -0,005 | -0,012 | -0,019 / +0,105 |
| N20_S3 | 711 | -0,046 | 289 | -0,011 | -0,016 | -0,006 / +0,101 |
| N55_S2 | 361 | +0,004 | 151 | +0,137 | +0,128 | +0,126 / +0,469 |
| N55_S3 | 319 | -0,017 | 127 | +0,171 | +0,165 | +0,093 / +0,311 |
| N100_S2 | 213 | +0,187 | 105 | +0,111 | +0,103 | +0,244 / +0,853 |
| N100_S3 | 189 | +0,080 | 85 | +0,147 | +0,142 | +0,242 / +0,684 |

E = espérance après spread/slippage. **Les 6 variantes sont rejetées ; l'OOS 2023-2026 n'a pas été ouvert** (il reste vierge).

Ce que les chiffres disent :
- N = 20 perd en entraînement et en validation, même avant swaps.
- N = 55 et 100 sont positifs par endroits, mais **le gain vient surtout d'USDJPY** (65 à 100 % du gain d'entraînement
  pour N100), sur 4 à 6 marchés positifs sur 12, avec 36 à 55 % d'années positives : pas de diversification réelle.
- Aucune variante ne bat le 95e centile des entrées aléatoires. Les entrées aléatoires avec les MÊMES sorties ont une
  médiane positive pour N55/N100 en 2020-2022 : l'espérance observée vient en grande partie de la règle de sortie et de la
  période (fortes tendances), pas du signal d'entrée.
- Les swaps (valeurs 2026 appliquées au passé) coûtent beaucoup : net d'entraînement N20_S2 -87,8 R contre -36,8 R après
  spread/slippage. À prendre avec prudence (approximation).

Ce qu'ils ne disent pas :
- Pas que le suivi de tendance « ne marche pas » : seulement que CE breakout, avec CES 6 réglages, sur CES 12 marchés et ce
  découpage, ne montre pas d'avantage robuste.

Limite du protocole constatée (non corrigée après coup) : le seuil de 15 trades par marché rend le critère « ≥ 7 marchés
positifs » impossible à satisfaire en validation pour N55/N100 (0 à 4 marchés éligibles). Le rejet tient sans ce critère
(échecs en entraînement : marchés positifs, concentration USDJPY, années positives, benchmark, plateau). À rediscuter avant
la prochaine expérience.
