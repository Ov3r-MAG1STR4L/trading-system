# Revue de l'expérience 003 (retournement à court terme après une séance extrême)

**Date :** 2026-10-28. **Base :** lancement au commit `72eb025`, protocole v0.4.2. Lecture seule des résultats de
`experiments/003-reversion-seance-extreme/` ; deux contrôles d'implémentation recalculés sur les données
d'entraînement et de validation déjà utilisées (aucune donnée OOS, aucun résultat modifié).

## Conclusion
**Le retour à la moyenne après une séance extrême n'apporte aucune valeur prédictive dans l'univers et sur la période
testés (12 marchés, 2012-2022) ; pour plusieurs seuils, il semble même aller dans la mauvaise direction.**
6/6 REJECT. Ce n'est pas une affirmation générale sur le forex ni sur les marchés.

## 1. Les rejets sont-ils indépendants ?
| Variante | Critères en échec (entraînement / validation) | Plateau |
|---|---|---|
| z=1,5, H=3 | 5 / 7 | non |
| z=1,5, H=5 | 5 / 6 | non |
| z=2,0, H=3 | 5 / 6 | non |
| z=2,0, H=5 | 5 / 6 | non |
| z=2,5, H=3 | 1 / 1 (échantillon) | non |
| z=2,5, H=5 | 1 / 1 (échantillon) | non |

- **z = 1,5 et 2,0** : espérance négative, profit factor < 1,10, stress négatif, trop peu de marchés positifs et
  d'années positives, benchmark non battu, dans les DEUX périodes. Les rejets ne dépendent d'aucun critère isolé.
- **z = 2,5** : 75-76 trades en entraînement (minimum 150) et 38-39 en validation (minimum 60). Quand le minimum de trades
  n'est pas atteint, le protocole n'évalue pas les autres critères : le rejet repose donc sur l'échantillon dans les deux
  périodes, plus l'absence de plateau. Pour information seulement : z=2,5, H=3 est légèrement positif en entraînement
  (+0,021 R) puis très négatif en validation (-0,251 R, 39 trades) ; ses trades viennent surtout des indices
  (US500, US30 : 30 sur 76 en entraînement).

## 2. Seuils d'échantillon de z = 2,5
Le faible nombre de trades est attendu : une séance de ±2,5 ATR est rare. 75 trades sur 7,4 ans et 12 marchés, soit
environ 1 par marché et par an. Ce n'est pas un problème d'implémentation : le benchmark, avec les mêmes contraintes,
prend 37-38 trades en moyenne en validation, comme la stratégie.

## 3. Benchmark et percentiles
- Recalculés depuis les 200 tirages conservés : **P95 et percentiles identiques** aux valeurs stockées, pour les
  6 variantes (méthode « linear », % des tirages strictement inférieurs).
- Les 200 graines sont distinctes et aucun tirage n'est vide.
- Médiane des tirages : entre -0,011 et +0,009 R. Avec une **sortie au temps identique**, des entrées aléatoires donnent
  environ zéro avant coûts : le benchmark ne transmet plus d'information de sortie, contrairement à 001 et 002.
- La stratégie est au **0e à 5e percentile** pour 4 variantes (z=1,5 H=5 ; z=2,0 H=3 et H=5 ; z=2,5 H=3), et aux
  29,5-34,5e percentiles pour les 2 autres : 131 à 200 tirages sur 200 font mieux qu'elle.
- Nuance : les tirages prennent 3 à 12 % de trades de moins que la stratégie (un signal aléatoire tombé pendant une
  position ouverte est ignoré). L'écart ne peut pas expliquer un percentile de 2,5 %.

## 4. Le résultat négatif vient-il d'un problème d'implémentation ?
Non, d'après deux contrôles indépendants :
1. **Trades réels** : les 943 trades de z=1,5, H=3 (entraînement et validation) correspondent tous à une séance extrême du
   bon sens (long après m ≤ -1,5, short après m ≥ +1,5), avec l'entrée à l'ouverture suivante, un stop de 2 × ATR(20) de
   la bougie du signal et une sortie au temps exactement à i+3. **0 incohérence.**
2. **Calcul sans le moteur** : le rendement « ouverture s+1 → ouverture s+1+H », dans le sens de la stratégie et en unités
   de 2 ATR, est **négatif dans les 8 combinaisons** (z = 1,5 et 2,0 ; H = 3 et 5 ; entraînement et validation), de -0,02 à
   -0,31, avec seulement 41 à 49 % de cas positifs. Sans stop ni coûts, le signe est le même : le résultat vient des
   prix, pas du moteur.

## 5. Coûts
Le résultat est négatif **avant** coûts (« brut ») pour z = 1,5 et 2,0. Le spread coûte environ 0,01 R par trade et les
swaps sont faibles sur des positions de 3 à 5 jours. Les coûts n'expliquent pas le rejet.

## 6. Ce qu'il ne faut pas faire maintenant
- **Ne pas tester tout de suite la stratégie inverse** (suivre la séance extrême). Elle serait directement inspirée par
  ce résultat. Si elle est étudiée un jour, ce sera une **nouvelle hypothèse** écrite et justifiée avant tout test, avec
  une grille fixée à l'avance et la mention explicite que 003 l'a motivée. Le compteur global de variantes (18) en tient
  compte.
- **Ne pas ouvrir l'OOS.** Aucune variante n'est candidate : l'OOS 2023-2026 reste une réserve intacte, jamais utilisée
  pour sélectionner une stratégie. Rappel : la famille « retour à la moyenne » avait été regardée de façon informelle
  sur 2023-2026 avant le laboratoire (journal 002, TradingView 4H).

## 7. Bilan méthodologique
Le benchmark v0.4.2 a apporté ce qui manquait en 001 et 002 : avec un stop, une sortie au temps et des coûts identiques,
la différence entre stratégie et benchmark porte directement sur le **timing d'entrée**. La distribution complète a
permis de recalculer et de vérifier chaque percentile.
