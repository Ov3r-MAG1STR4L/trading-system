# Revue de l'expérience 002 (momentum en série temporelle)

**Date :** 2026-10-28. **Base :** résultats commités en `b263952` (lancement `172705d`). Aucune nouvelle exécution :
cette revue lit uniquement `experiments/002-momentum-serie-temporelle/` (décision, rapports par variante et période).
Les résultats et critères de 002 ne sont pas modifiés.

## Conclusion
**Aucune des six variantes prédéfinies ne démontre un avantage suffisamment robuste selon le protocole v0.4.1.**
Ce n'est pas une preuve que « le momentum ne marche pas ». C'est le comportement attendu du laboratoire : une variante
peut être positive en validation et être rejetée si elle ne franchit pas les autres garde-fous.

## 1. Les 6 rejets sont-ils indépendants ?
Oui. Chaque variante échoue sur **au moins deux critères indépendants** : retirer n'importe quel critère isolé ne
changerait aucune décision.

| Variante | Motifs | Motifs de rejet |
|---|---|---|
| L60_K3 | 2 | concentration USDJPY 67 % (validation) ; benchmark non battu |
| L60_K5 | 2 | concentration USDJPY 70 % (validation) ; benchmark non battu |
| L125_K3 | 4 | EURUSD 48 % et 22 pertes d'affilée (entraînement) ; USDJPY 54 % et benchmark (validation) |
| L125_K5 | 3 | EURUSD 47 % et 22 pertes d'affilée (entraînement) ; benchmark (validation) |
| L250_K3 | 4 | AUDUSD 48 % (entraînement) ; 5/11 marchés positifs, USDJPY 62 %, benchmark (validation) |
| L250_K5 | 5 | AUDUSD 43 % et 50 % d'années positives (entraînement) ; USDJPY 64 %, années, benchmark (validation) |

## 2. L60 près du seuil du benchmark : faut-il une analyse complémentaire ?
**Non.** L60 est à +0,035 R contre un 95e centile de +0,039 R (k=3), et à égalité pour k=5 (+0,019 R). Mais :
- même si le benchmark était passé, la **concentration USDJPY rejette L60 à elle seule** ;
- **sans USDJPY**, l'espérance de validation tombe à **+0,012 R (k=3) et +0,006 R (k=5)**, c'est-à-dire presque rien ;
- refaire une analyse sur la validation après avoir vu les résultats reviendrait à ajuster après coup.

Le fait notable reste vrai : la médiane des entrées aléatoires est négative pour L60 (-0,02 R) alors que la stratégie
est positive. Le signal porte peut-être un peu d'information, mais pas assez pour le protocole.

## 3. Le benchmark aléatoire : deux constats de méthode
1. **Les sorties transmettent une partie du signal au benchmark.** Le benchmark garde les mêmes sorties que la
   stratégie. Or, pour le momentum, la sortie d'un long est « le rendement sur L jours devient ≤ 0 ». Un long aléatoire
   ouvert pendant une baisse sort donc presque aussitôt, tandis qu'un long ouvert pendant une hausse la suit. Le
   benchmark n'est donc pas un « pur hasard » : il hérite du filtre de tendance de la stratégie. Ça rend le test plus
   exigeant, mais il mesure surtout la valeur de l'**entrée**, pas celle de la stratégie entière. C'est cohérent avec
   001 (avec les mêmes sorties, des entrées aléatoires y faisaient aussi bien).
2. **La distribution complète des 200 tirages n'est pas conservée.** Seuls la médiane et le 95e centile sont dans
   `decision.json`, ainsi que le nombre de signaux demandés, mais pas le nombre de trades réellement pris par les
   tirages (le moteur ignore un signal pendant une position ouverte). Les centiles exacts de L60 ne sont donc pas
   recalculables sans réexécution.

Ces deux points ne changent aucune décision de 002. Ils sont à traiter **avant 003**, par une décision de protocole
prise indépendamment des résultats (par exemple : conserver la distribution complète ; ajouter un second benchmark
dont les sorties ne dépendent pas du signal).

## 4. Concentration
- La validation 2020-2022 est dominée par **USDJPY** pour 5 variantes sur 6 (54 à 70 % du gain), comme en 001.
- L'entraînement est dominé par **EURUSD** (L125) ou **AUDUSD** (L250), à 43-48 %.
- Seul L60 est diversifié en entraînement (USDJPY 27 %, 10 marchés positifs sur 12), mais pas en validation.
- Lecture : sur cet univers, les gains de suivi de tendance de 2020-2022 viennent surtout d'une tendance (USDJPY).
  Une stratégie qui ne « marche » que par USDJPY n'est pas diversifiée.

## 5. Après coûts ou net : deux lectures à ne pas confondre
| Variante | Entraînement après spread/slippage | Entraînement net | Validation après spread/slippage | Validation net |
|---|---|---|---|---|
| L60_K3 | +95,5 R | +47,6 R | +18,2 R | +6,0 R |
| L60_K5 | +57,5 R | +28,4 R | +9,6 R | +2,2 R |
| L125_K3 | +29,7 R | -8,8 R | +22,5 R | +11,4 R |
| L125_K5 | +18,4 R | -6,6 R | +21,2 R | +13,1 R |
| L250_K3 | +20,2 R | -10,7 R | +17,1 R | +10,5 R |
| L250_K5 | +14,7 R | -6,0 R | +10,0 R | +5,9 R |

- Les décisions du protocole se prennent sur le résultat **après spread et slippage**, qui est mesuré de façon fiable.
- Le **net** ajoute les swaps **actuels (2026) appliqués à 2012-2022** : c'est une approximation forte. Les taux étaient
  très différents (taux proches de zéro jusqu'en 2021). Le net est donc une indication de sensibilité aux swaps, pas un
  résultat historique. Il montre que les positions longues de cette famille rendent le swap déterminant.

## 6. Exposition
Le maximum mesuré de 4,4 % vient du retournement : la position fermée et la nouvelle sont comptées ensemble le jour
du retournement. Il n'y a jamais plus d'une position par marché : ce n'est pas un dépassement du risque de 3 %.

## 7. Avant 003
- Ne pas empiler des stratégies jusqu'à ce qu'une variante passe : 12 variantes testées sur les mêmes données
  d'entraînement et de validation, le risque de faux positif augmente à chaque expérience.
- Décider d'abord, indépendamment des résultats : le traitement des deux constats sur le benchmark (section 3).
- OOS 2023-2026 : toujours vierge.
