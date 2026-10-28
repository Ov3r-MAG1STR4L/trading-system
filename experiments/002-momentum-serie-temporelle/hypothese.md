# 002 — Momentum en série temporelle (proposition, NON lancée)

**Date :** 2026-10-28 (écrit AVANT tout code de stratégie et toute exécution)
**Protocole :** v0.4.1 (`docs/protocole-recherche-v0.4.md`)
**Statut :** Proposition — en attente de validation. Aucune variante exécutée, OOS fermé.

## 1. Problème
L'expérience 001 a montré que le breakout de Donchian n'apportait pas d'avantage robuste : gain concentré sur USDJPY,
moins de la moitié des marchés positifs, et **des entrées aléatoires avec les mêmes sorties faisaient aussi bien**.
L'entrée « cassure d'un plus haut » n'apportait donc pas d'information mesurable dans ce cadre.

Question de 002 : **une autre définition de la tendance, la direction du rendement passé sur une longue période
(momentum en série temporelle), apporte-t-elle un avantage mesurable par rapport à des entrées aléatoires, après coûts,
sur plusieurs marchés ?**

## 2. Pourquoi après Donchian
- C'est la forme de suivi de tendance la mieux documentée dans la littérature académique sur longue période et sur
  plusieurs classes d'actifs (« time-series momentum »).
- Elle se distingue de 001 par la nature du signal (rendement sur L jours au lieu d'une cassure de canal), pas par un
  réglage plus fin : ce n'est pas une variante optimisée de 001.
- Elle reste simple : 2 paramètres libres, aucun filtre ajouté.
- Le choix vient du raisonnement sur l'échec de 001 (entrée peu informative), pas d'un résultat chiffré qui la
  favoriserait. Aucune donnée de 2023-2026 n'a été regardée.

## 3. Stratégie exacte
À la clôture de la bougie i, en n'utilisant que les bougies ≤ i :
- `r = close[i] / close[i - L] - 1` (rendement sur L bougies du marché) ;
- **entrée** seulement quand le signe de r CHANGE : long si r passe de ≤ 0 à > 0, short s'il passe de ≥ 0 à < 0
  (pas de réentrée automatique après un stop : il faut un nouveau changement de signe) ;
- **stop** = k × ATR(20) de la bougie i, fixé à l'entrée et jamais déplacé ;
- **sortie** d'un long quand r redevient ≤ 0, d'un short quand r redevient ≥ 0 ;
- pas d'objectif ; exécution par le moteur à l'ouverture de i+1 ; une position par marché ;
- chauffe : aucune entrée tant que L + 20 bougies ne sont pas disponibles.

## 4. Paramètres et budget
| Paramètre | Valeurs autorisées | Raison du choix (a priori) |
|---|---|---|
| L (bougies de rendement) | 60, 125, 250 | environ 3, 6 et 12 mois, horizons standards de la littérature |
| k (stop en ATR) | 3, 5 | stop de catastrophe large : la sortie normale est le changement de signe |

- **2 paramètres libres, 6 variantes**, sous le budget du protocole (≤ 3 paramètres, ≤ 3 valeurs chacun).
- Aucune autre variante, aucun filtre, aucun paramètre ajouté après observation.
- Les 6 variantes seront inscrites au registre global **au lancement, avant toute évaluation** (comme 001) :
  compteur après 002 = 12 variantes.
- Voisinage pour le plateau : même L avec l'autre k ; même k avec le L adjacent.

## 5. Données, périodes, risque
- 12 marchés de `config/marches.csv`, D1, mêmes règles partout.
- Entraînement 2012-08-06 → 2019-12-31 ; validation 2020-01-01 → 2022-12-31 ; données **tronquées à la fin de chaque
  période** par `src/recherche.py`.
- **OOS 2023-01-01 → 2026-10-27 fermé.** Il ne serait ouvert qu'une fois, pour la meilleure variante KEEP, et seulement
  après ta décision explicite (voir point 10).
- Risque : 0,25 % du capital réalisé par trade, sans plafond, exposition mesurée.

## 6. Coûts
- Spread = max(spread de la bougie, médiane des spreads > 0 du marché sur 2012-2022).
- Slippage : 0 (base) et 1 × plancher de spread par exécution (stress).
- Swaps : relevé v0.4 (forex, métaux, indices convertis) ; valeurs ACTUELLES appliquées au passé, approximation.
  Les positions longues de cette stratégie rendent les swaps importants : le net sera toujours rapporté séparément.

## 7. Benchmark
200 tirages d'entrées aléatoires sur la validation (graine fixe) : mêmes marchés, même nombre de signaux par marché,
**mêmes stops et mêmes sorties** que la variante. Rejet si l'espérance ne dépasse pas le 95e centile.

## 8. Critères (protocole v0.4.1, sur R après spread et slippage)
- **REJECT** si un seul critère échoue, en entraînement ou en validation :
  - espérance ≤ 0 ou profit factor < 1,10 ;
  - stress négatif ;
  - moins de 150 trades en entraînement ou de 60 en validation ;
  - moins de 5 marchés positifs, ou pas plus de 50 % des marchés éligibles ;
  - un marché fait plus de 40 % du gain ;
  - drawdown réalisé > 25 % ;
  - série de pertes > 20 ;
  - moins de 60 % d'années positives ;
  - benchmark non battu ;
  - pas de plateau.
- **NEEDS_REVIEW** : aucun rejet, mais un indicateur à moins de 10 % d'un seuil, ou une année qui fait plus de 50 % du gain.
- **KEEP** : aucun critère en échec. KEEP veut dire « candidat à l'OOS », jamais « rentable ».
- Échantillon par marché : `< 5` trades = `INSUFFICIENT_SAMPLE` (ni positif ni négatif, hors dénominateur) ;
  `≥ 5` éligible ; `≥ 15` information seulement.

## 9. Ce qui serait intéressant, indépendamment de la rentabilité
- **La comparaison au benchmark aléatoire.** Si 002 fait mieux que des entrées aléatoires alors que 001 n'y arrivait
  pas, c'est une information sur la valeur du signal, même si la stratégie reste négative après coûts.
- **La concentration.** USDJPY domine-t-il encore ? Si oui, le « suivi de tendance » observé sur cet univers serait
  surtout un effet USDJPY de 2012-2022.
- **Le poids des swaps sur des positions longues.** Il dira si cette famille est réaliste avec ce broker.
- **Le nombre de trades par marché en validation.** Il testera la règle v0.4.1 (combien de marchés sont
  `INSUFFICIENT_SAMPLE` pour L = 250).

## 10. Points de vigilance déclarés avant le test
- La période d'entraînement + validation a déjà été utilisée par 001 : chaque nouvelle expérience sur les mêmes données
  augmente le risque de trouver un résultat par hasard. Le compteur global (12 après 002) sert à le garder en tête.
- La stratégie est presque toujours en position : l'exposition simultanée sera proche du maximum (12 × 0,25 % = 3 %).
- Le minimum de 150 trades en entraînement peut être difficile à atteindre pour L = 250 (peu de changements de signe) :
  c'est un rejet possible par manque d'échantillon, déclaré avant le test.
- L'ouverture de l'OOS, si une variante était KEEP, est faite automatiquement par le script de 001. Pour 002, je propose
  qu'elle ne soit **pas automatique** : le script s'arrêterait après la validation, et l'OOS ne s'ouvrirait qu'après ton accord.
