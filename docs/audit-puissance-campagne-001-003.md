# Audit de puissance statistique — laboratoire après la campagne 001-003

**Date :** 2026-10-28. **Base :** commit `b908895`, tag `campaign-001-003`, protocole v0.4.2.
**Nature :** audit méthodologique indépendant, réalisé en lecture seule. Ce n'est pas une revue d'expérience.
Aucun backtest, aucun benchmark relancé, aucune donnée OOS, aucun résultat ni critère modifié.

**Décision C — les données actuelles sont insuffisantes pour poursuivre une campagne de recherche de stratégie avec ce
niveau de puissance.**

## 1. Périmètre
- **18 variantes** issues des expériences 001, 002 et 003 (6 chacune), toutes REJECT.
- Analyse principale sur les **résultats de validation** (2020-2022) commités : une valeur `R_execution` (R après spread et
  slippage) par trade. Les rapports d'entraînement ne servent qu'aux comparaisons.
- **Aucun backtest supplémentaire.**
- **Benchmark complet (200 tirages) disponible seulement pour 003.** Pour 001 et 002, seuls la médiane et le P95 ont été
  conservés dans `decision.json` : leur distribution et le percentile de la stratégie n'existent pas.

## 2. Formules
- Erreur type de l'espérance : **ET = σ / √n** (σ : écart-type empirique des R par trade ; n : nombre de trades).
- Effet minimal détectable, test unilatéral au seuil de 5 % : **MDE = k × ET**,
  avec **k = z(0,95) + z(0,80) = 2,49** à 80 % de puissance et **k = z(0,95) + z(0,90) = 2,93** à 90 %.
- Trades nécessaires pour un avantage vrai E : **n = (k × σ / E)²**.
- Puissance réelle pour un avantage vrai E : **1 − Φ(1,645 − E / ET)**.
- L'approximation normale n'est qu'une première lecture ; elle a été complétée par un bootstrap simple (4 000
  rééchantillonnages) et un bootstrap par grappes mensuelles (trades corrélés au sein d'un même mois).

## 3. Puissance par expérience (validation)
| Expérience | Trades médians (min-max) | σ médian | ET normale | ET par grappes mensuelles | MDE 80 % | MDE 90 % |
|---|---:|---:|---:|---:|---:|---:|
| 001 | 139 (85-306) | 2,14 | 0,181 | 0,196 | ~0,45 R | ~0,53 R |
| 002 | 339 (235-517) | 0,86 | 0,048 | 0,057 | ~0,12 R | ~0,14 R |
| 003 | 96 (38-288) | 0,83 | 0,088 | 0,084 | ~0,22 R | ~0,26 R |

- Le bootstrap simple donne une erreur type presque identique à la formule normale (0,025 à 0,35 R selon la variante).
- La corrélation des trades d'un même mois multiplie l'erreur type par **1,0 à 1,5** (médiane 1,13 à 1,21).
- Toutes les variantes de 002 ont un intervalle de confiance à 95 % qui contient zéro ; la meilleure, L125_K5
  (+0,062 R), a un intervalle bootstrap de [-0,016 ; +0,155] R.

**Trades nécessaires pour détecter un avantage vrai** (σ médian de chaque expérience ; 80 % / 90 % de puissance) :
| E vrai | 001 (σ = 2,14) | 002 (σ = 0,86) | 003 (σ = 0,83) |
|---|---:|---:|---:|
| +0,02 R | 70 551 / 97 725 | 11 345 / 15 714 | 10 766 / 14 912 |
| +0,03 R | 31 356 / 43 434 | 5 042 / 6 984 | 4 785 / 6 628 |
| +0,05 R | 11 289 / 15 636 | 1 816 / 2 515 | 1 723 / 2 386 |
| +0,10 R | 2 823 / 3 909 | 454 / 629 | 431 / 597 |

**Puissance réelle avec les tailles obtenues** (médiane ; entre parenthèses, avec les grappes mensuelles) :
| | +0,02 R | +0,03 R | +0,05 R | +0,10 R |
|---|---:|---:|---:|---:|
| 001 | 6 % | 7 % | 9 % (8 %) | 14 % (13 %) |
| 002 | 11 % (10 %) | 16 % (13 %) | 28 % (22 %) | 68 % (54 %) |
| 003 | 8 % | 10 % | 14 % (15 %) | 31 % (33 %) |

**D'où vient le manque de puissance** (pour détecter +0,05 R à 80 %) :
- 001 : il faudrait **81 fois** plus de trades, ou un σ **9 fois** plus faible : la dispersion domine.
- 002 : **5,4 fois** plus de trades, ou un σ **2,3 fois** plus faible : les deux pèsent.
- 003 : **18 fois** plus de trades, ou un σ **4,2 fois** plus faible : le nombre de trades domine.

## 4. Benchmark
- **003** possède les 200 tirages complets par variante. P50, P95 et percentiles ont été **recalculés et vérifiés**
  identiques aux valeurs stockées. L'écart-type des espérances des tirages (0,035 à 0,118 R) est proche de l'erreur type
  de la stratégie (0,046 à 0,161 R) ; l'écart P95 − P50 vaut 0,05 à 0,21 R. Pour passer le P95 avec une puissance
  raisonnable, une entrée devrait battre le hasard d'environ 0,09 R (z = 1,5, H = 3) à 0,2-0,3 R (z = 2,5).
- **001 et 002** ne possèdent pas leur distribution complète. Le benchmark v0.4.2 est exploitable proprement pour 003,
  mais **pas rétroactivement** pour calculer les percentiles de 001 et 002.

## 5. Tests multiples
Ordres de grandeur méthodologiques ; **les variantes ne sont pas indépendantes**.
| Variantes testées | P(au moins un faux positif) sous indépendance, seuil 5 % |
|---:|---:|
| 6 | ~26,5 % |
| 12 | ~46 % |
| 18 | ~60,3 % |

- **Corrélations observées** (résultats mensuels de validation, 36 mois) : en moyenne 0,36 au sein de 001, 0,19 au sein
  de 002, 0,63 au sein de 003, et 0,07 entre expériences.
- **Nombre effectif de tests** estimé entre **environ 10** (méthode de Li et Ji) **et 16** (méthode de Nyholt).
- **Risque effectif approximatif d'au moins un faux positif : de l'ordre de 40 à 56 %.**
- **Bonferroni sur 18** : seuil d'environ **0,28 %** ; le facteur k passe de 2,49 à 3,61, soit des MDE multipliés par
  environ **1,45** et des tailles d'échantillon nécessaires multipliées par environ 2,1.
- Aucune correction définitive n'est choisie ici.

## 6. Limites
- **σ mesuré sur des stratégies rejetées** : une stratégie ayant un vrai avantage pourrait avoir une dispersion
  différente.
- **Queues épaisses et asymétrie** (asymétrie de 4 à 7 pour 001 et 002) : les puissances calculées par la loi normale
  restent approximatives.
- **Bootstrap par grappes mensuelles** limité par le faible nombre de mois (36 en validation, 13 pour z = 2,5).
- **Validation 2020-2022 déjà vue trois fois** (001, 002, 003) : ce n'est plus une réserve indépendante.
- **Données D1 d'un seul courtier** (MetaQuotes démo), 12 marchés.
- **Absence** d'historique des taux, de volume réel, de données fondamentales et de données intraday.
- **OOS 2023-2026 vierge** : il n'a pas été utilisé, y compris dans cet audit. À titre indicatif, il offrirait de l'ordre
  de 400 à 650 trades pour une stratégie comparable à 002, soit un MDE d'environ 0,09-0,10 R sans correction et
  0,13-0,15 R avec.

## 7. Conclusion
**Décision C — les données actuelles sont insuffisantes pour poursuivre une campagne de recherche de stratégie avec ce
niveau de puissance.**
- Le laboratoire peut détecter des effets **relativement gros** (de l'ordre de 0,12 R par trade et plus pour une
  dispersion comme celle de 002 ; 0,2 à 0,45 R pour 001 et 003), ou rejeter une idée nettement mauvaise, comme 003.
- Il est **mal adapté** à la détection d'avantages réalistes de l'ordre de **+0,02 à +0,05 R par trade** : il faudrait
  de 1 700 à plus de 10 000 trades selon la dispersion, contre 38 à 517 trades par variante en validation.
- Ajouter des expériences sur les mêmes données augmenterait surtout le **risque de sélection et de faux positifs**.
- Une correction des tests multiples **réduirait encore** la puissance (MDE × ~1,45).
- Il est donc préférable de **ne pas lancer d'expérience 004**.

## 8. Ce que la décision C signifie
C **ne signifie pas** : « aucune stratégie ne fonctionne ».

C signifie : **« avec les données, l'univers et le protocole actuels, nous ne pouvons pas établir de manière suffisamment
fiable qu'une petite stratégie possède un avantage réel. »**

C'est une décision d'arrêt méthodologique, pas une conclusion générale sur le trading.

## 9. Conditions éventuelles de reprise
Seules voies acceptables pour une reprise future (aucune n'est choisie ici, aucune stratégie ni grille n'est proposée) :
- beaucoup plus de trades **indépendants** ;
- davantage de marchés ;
- un historique plus long ;
- éventuellement une fréquence plus élevée, si des données fiables sont disponibles ;
- des stratégies à dispersion plus faible ;
- une correction des tests multiples définie **avant** toute nouvelle campagne.
