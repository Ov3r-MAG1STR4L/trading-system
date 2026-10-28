# Proposition d'expérience 003 — retournement à court terme après un mouvement extrême

**Statut : VALIDÉE le 2026-10-28, telle quelle** (durée maximale de détention comprise). Au moment de la validation :
aucun code de stratégie, aucune inscription au registre, aucune exécution, aucun dossier `experiments/003-…`.
Sémantique validée de la durée : entrée à l'ouverture de i, sortie à l'ouverture de i+H (H séances complètes).
**Protocole visé : v0.4.2** (première expérience sous ce protocole). **OOS 2023-2026 : fermé.**

## 1. Question scientifique

**Ce qu'on a appris :**
- **001 (Donchian)** : avec les mêmes sorties, des entrées aléatoires faisaient aussi bien. La cassure d'un plus haut
  n'apporte pas d'information mesurable dans ce cadre.
- **002 (momentum en série temporelle)** : un peu plus d'information à l'entrée (médiane aléatoire négative pour L60),
  mais pas au-delà du P95, et un gain qui dépend d'USDJPY.
- **Les deux expériences testent la même source d'information** : la persistance des tendances. Les deux faiblesses
  communes : peu d'information à l'entrée, et un résultat qui dépend de quelques grandes tendances (USDJPY 2020-2022).

**Question de 003 :** *une source d'information OPPOSÉE et à COURT terme, la sur-réaction d'une séance, apporte-t-elle
un meilleur timing d'entrée que le hasard, sur plusieurs marchés, après coûts ?*

**Pourquoi c'est différent :**
- Signal de **retour à la moyenne** et non de tendance : il gagne quand le mouvement se corrige, pas quand il continue.
- **Horizon de quelques jours** au lieu de plusieurs semaines : les gains ne peuvent pas venir d'une seule grande tendance
  de plusieurs mois. Le critère de concentration devient un vrai test de diversification.
- **Sortie au temps**, indépendante du signal (voir section 3) : le benchmark v0.4.2 mesure alors le timing d'entrée
  de façon plus pure qu'en 001 et 002, où les sorties transmettaient une partie du signal.
- Ce n'est ni une nouvelle valeur de L, ni un nouveau stop, ni une sélection de marchés tirée de 002.

## 2. Signal (entrée)
À la clôture de la bougie i, avec les seules bougies ≤ i :
- `m[i] = (close[i] - close[i-1]) / ATR20[i-1]` : le mouvement de la séance en unités de volatilité **d'avant** la séance
  (ATR(20) calculé jusqu'à i-1, pour que la séance extrême ne gonfle pas sa propre mesure) ;
- **long** si `m[i] ≤ -z` (forte baisse), **short** si `m[i] ≥ +z` (forte hausse) ;
- exécution par le moteur à l'ouverture de i+1 ; une position par marché ; pas de retournement ;
- chauffe : pas d'entrée avant 21 bougies.

## 3. Sortie et gestion du risque
Pour ne pas changer plusieurs choses à la fois, tout ce qui n'est pas l'objet de l'expérience reste la convention du
laboratoire :
- **Stop fixe = 2 × ATR20 de la bougie du signal**, fixé à l'entrée, jamais déplacé. Ce n'est pas un paramètre : c'est la
  convention par défaut des expériences 001 et `strategies/exemple.py`.
- **Sortie au temps** : la position est fermée à l'ouverture de la bougie i+1+H, soit après H séances complètes, si le
  stop n'a pas été touché. Pas d'objectif.
- Risque : 0,25 % du capital réalisé par trade, sans plafond, exposition mesurée.
- Coûts : protocole v0.4.2 (spread plancher, stress = 1 plancher de slippage, swaps actuels appliqués au passé).

**Prérequis technique à valider :** le moteur ne sait pas aujourd'hui fermer une position « après H bougies ». Une
stratégie ne peut pas le faire elle-même, car elle ne connaît pas la date réelle d'entrée (un signal peut être ignoré si
une position est déjà ouverte). Il faudrait ajouter au moteur une **durée maximale de détention optionnelle**,
désactivée par défaut, testée séparément comme le retournement, avant toute stratégie 003. C'est une capacité
d'exécution générique : elle ne change ni le signal, ni le stop, ni les coûts.

## 4. Grille (fixée ici, avant tout code)
| Paramètre | Valeurs | Justification a priori |
|---|---|---|
| z (seuil du mouvement, en ATR) | 1,5 ; 2,0 ; 2,5 | de « séance forte » à « séance rare » ; des multiples entiers ou demi-entiers d'ATR, sans réglage fin |
| H (séances de détention) | 3 ; 5 | horizons courants de la littérature sur le retournement à court terme (de l'ordre d'une semaine) |

**2 paramètres, 6 variantes**, sous le budget (≤ 3 × 3). Aucune valeur n'est tirée des résultats de 001 ou 002.
Compteur global après 003 : 18 variantes. Voisinage du plateau : même z avec l'autre H ; même H avec le z adjacent.

## 5. Benchmark v0.4.2
Benchmark d'entrées randomisées à sorties identiques : même stop de 2 ATR, même sortie après H séances, mêmes coûts,
même période ; seules la date et le sens d'entrée sont randomisés. 200 tirages, graines `[graine, k]`, centile
« linear », distribution complète dans `benchmark/<variante>.json`, percentile empirique rapporté. Critère : espérance
strictement supérieure au P95. Aucun changement du nombre de tirages ou des graines après observation.

## 6. Critères (protocole v0.4.2 inchangé)
- Entraînement et validation : espérance > 0 et profit factor ≥ 1,10 après coûts ; stress positif ;
  ≥ 150 trades en entraînement et ≥ 60 en validation.
- Marchés : éligibles à ≥ 5 trades ; ≥ 5 marchés positifs ET majorité stricte des éligibles.
- Concentration ≤ 40 % ; ≥ 60 % d'années positives ; drawdown réalisé ≤ 25 % ; série de pertes ≤ 20 ; plateau ;
  benchmark P95.
- NEEDS_REVIEW / KEEP comme dans le protocole. KEEP veut dire « candidat à l'OOS », jamais « rentable ».

## 7. OOS
Le script de 003 s'arrêtera après la validation (`VALIDATION_COMPLETE — OOS_LOCKED`), même si une variante semble
excellente. L'OOS ne s'ouvrira que par une action séparée, après ta décision.

## 8. Ce qui serait informatif, même en cas de rejet
- Le **percentile empirique** contre des entrées aléatoires ayant exactement les mêmes sorties au temps : la mesure la
  plus directe à ce jour de la valeur d'un timing d'entrée.
- La **diversification** : un signal de quelques jours est-il moins concentré qu'un signal de tendance ?
- La **sensibilité aux coûts** : beaucoup de trades courts, donc un spread proportionnellement lourd. Le stress test
  dira si l'idée survit à des coûts réalistes.

## 9. Points de vigilance déclarés avant le test
- **Contamination partielle de l'OOS pour cette famille.** Avant le laboratoire, le journal 002 (RSI, TradingView) a
  testé un retour à la moyenne en 4H sur **2023-2026** (EURUSD, GBPUSD, USDJPY, AUDUSD), soit notre période OOS. Le signal,
  l'unité de temps et les règles diffèrent, et ce test a été rejeté, mais la période a été regardée pour cette famille
  d'idées. À garder en tête si l'OOS était un jour ouvert pour 003.
- Les données d'entraînement et de validation sont réutilisées pour la 3e fois (18 variantes au total) : le risque de
  faux positif augmente.
- Coûts : avec des positions de 3 à 5 jours, le spread pèse plus qu'en 001 et 002 ; les swaps beaucoup moins.
- Il faut ajouter au moteur la durée maximale de détention (section 3) : c'est une étape à valider et tester avant la
  stratégie.

## 10. Pistes écartées, pour mémoire
- **Carry (écart de taux)** : nécessite l'historique des taux ou des swaps, que nous n'avons pas (seulement les swaps
  actuels). Impossible à tester honnêtement.
- **Momentum transversal** (classer les marchés entre eux) : autre forme de momentum, trop proche de 002.
- **Breakout de volatilité** : famille breakout, trop proche de 001.
- **Saisonnalité calendaire** : hypothèse a priori faible sur le forex, et 12 marchés hétérogènes.
