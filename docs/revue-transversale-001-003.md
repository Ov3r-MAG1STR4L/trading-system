# Revue transversale des expériences 001 à 003

**Date :** 2026-10-28. Lecture seule des résultats commités ; aucun résultat, paramètre ni critère modifié.
001, 002 et 003 sont **figées**. **OOS 2023-2026 : vierge.** Aucune expérience 004 n'est préparée.
**Décision (section 7) : option C, la campagne 001-003 est terminée.**

## 1. Bilan
| | 001 Donchian | 002 Momentum en série temporelle | 003 Retour à la moyenne après séance extrême |
|---|---|---|---|
| Source d'information | cassure d'un canal (tendance) | signe du rendement sur L jours (tendance) | sur-réaction d'une séance (contre-tendance) |
| Horizon | semaines | semaines à mois | 3 à 5 séances |
| Protocole | v0.4 | v0.4.1 | v0.4.2 |
| Décision | 6/6 REJECT | 6/6 REJECT | 6/6 REJECT |
| Candidat à l'OOS | aucun | aucun | aucun |

**18 variantes testées, aucune n'a justifié l'ouverture de l'OOS.**

## 2. Comparaison sur des critères communs (après spread et slippage)
| Critère | 001 | 002 | 003 |
|---|---|---|---|
| Espérance en entraînement | -0,048 à +0,187 R | +0,024 à +0,079 R | -0,088 à +0,021 R |
| Espérance en validation | -0,011 à +0,171 R | +0,019 à +0,073 R | -0,251 à -0,011 R |
| Cohérence entraînement → validation | faible (signes qui changent) | bonne (positif partout) | négatif partout pour z = 1,5 et 2,0 |
| Profit factor en validation | 0,97 à 1,35 | 1,14 à 1,44 | 0,43 à 0,96 |
| Concentration du gain (validation) | USDJPY 62 à 211 % | USDJPY 54 à 70 % (5 variantes sur 6) | sans objet (pas de gain) |
| Marchés positifs (validation) | règle v0.4, non comparable | 5 à 8 sur 11-12 | 1 à 4 sur 4-12 |
| Années positives (entr. + valid.) | 36 à 55 % | 50 à 82 % | 0 à 37 % |
| Avant coûts | positif pour N55/N100 | positif | **déjà négatif** |
| Poids des swaps | important | important (net négatif en entraînement pour L125/L250) | faible |
| Benchmark | ancien, sorties qui transmettent le signal, distribution non conservée | ancien, idem | **v0.4.2 : sortie au temps, 200 tirages conservés** |
| Position contre le hasard | non battu (percentile inconnu) | non battu, proche du seuil pour L60 (percentile inconnu) | **0e à 5e percentile pour 4 variantes**, 29,5 à 34,5e pour 2 |

## 3. Les quatre questions

**Le suivi de tendance fonctionne-t-il ?** Pas de façon assez robuste selon le protocole. 002 est le plus proche : il est
positif en entraînement et en validation pour les 6 variantes, avec des profit factors de 1,14 à 1,44. Mais le gain de
validation dépend d'USDJPY, et aucune variante ne dépasse le benchmark. Dans cet univers, le gain observé sur 2020-2022
ressemble surtout à une grande tendance (USDJPY), pas à un avantage diversifié.

**Le timing contrariant fonctionne-t-il ?** Non. 003 est négatif avant coûts, en entraînement et en validation, et pour
plusieurs seuils nettement moins bon que des entrées aléatoires. Un contrôle sans le moteur donne le même signe.

**Le timing d'entrée apporte-t-il de l'information ?** Seule 003 le mesure proprement (sortie au temps identique au
benchmark). Elle montre une information **négative** pour ce signal : entrer contre la séance extrême fait moins bien que
le hasard. Pour 001 et 002, l'ancien benchmark ne permet pas de séparer l'entrée de la sortie : la question reste ouverte.

**Une stratégie mérite-t-elle l'OOS ?** Non. Aucune variante n'a passé les critères. L'OOS reste une réserve intacte et ne
sera pas utilisé pour « voir ce qui marche » sur 2023-2026.

## 4. Ce que les trois expériences disent ensemble
- Les deux familles de **tendance** donnent un peu de gain brut, mais concentré sur une seule grande tendance et non
  distingué du hasard.
- La famille **contrariante** est franchement négative, ce qui est cohérent avec une persistance des mouvements à court
  terme dans cet univers et sur cette période. Ce n'est qu'une **observation**, pas une hypothèse testée.
- Les **coûts** ne sont pas la cause principale des rejets : 003 est négatif avant coûts, et 001-002 échouent sur la
  robustesse avant d'échouer sur les coûts. Les **swaps** restent une approximation (valeurs 2026 appliquées au passé).
- Les **données** sont limitées : bougies D1 d'un seul courtier démo, 12 marchés, sans historique des taux, sans volume
  réel ni données fondamentales. Cela restreint les familles de signaux testables honnêtement.
- **Risque de faux positif cumulé** : 18 variantes sur les mêmes données d'entraînement et de validation. Avec un seuil
  au 95e centile, environ une variante sur vingt peut franchir le benchmark par hasard ; chaque expérience de plus
  augmente ce risque.

## 5. Options pour la suite (décision à prendre, rien n'est préparé)
**A. Une hypothèse réellement différente** (ni tendance, ni cassure, ni retour à la moyenne d'un mouvement récent).
- Avantage : apporterait une information nouvelle, indépendante des trois résultats.
- Difficulté : avec les seules bougies D1 de 12 marchés, les sources restantes (calendrier, relations entre marchés,
  structure de la volatilité) manquent d'une justification a priori solide. Une hypothèse choisie faute de mieux serait
  une recherche déguisée.
- Condition : une justification écrite qui tienne **avant** de regarder les données.

**B. Le momentum court terme dérivé de 003** (« une séance très forte annonce-t-elle une poursuite ? »).
- Avantage : question précise, mesurable avec le benchmark v0.4.2, et l'observation de 003 est nette.
- Risque : l'idée vient du résultat de 003 sur les mêmes données. Un succès serait en partie attendu par construction ;
  il faudrait le déclarer comme hypothèse **dérivée**, fixer la grille avant tout test, et considérer que la validation
  2020-2022 a déjà été « vue » pour cette question. L'OOS deviendrait alors le seul vrai juge, et resterait la seule
  ouverture possible.

**C. Arrêter les expériences ici.**
- Résultat : « aucune des hypothèses testées ne fournit assez de preuves pour justifier une validation hors échantillon ».
  C'est un résultat valide du laboratoire, pas un échec.
- Conserve l'OOS vierge pour une éventuelle hypothèse future mieux fondée, ou de nouvelles données.

## 6. Avis
- **A** n'est pas défendable aujourd'hui sans une idée justifiée indépendamment des données : je ne la recommande pas
  tant qu'une telle idée n'existe pas.
- Entre **B** et **C**, le choix dépend de l'objectif. Pour continuer à apprendre, **B est acceptable une seule fois**,
  comme hypothèse dérivée déclarée, avec une grille petite et fixée, en acceptant qu'un éventuel succès ne vaudrait
  qu'après un OOS unique. Pour préserver au maximum la valeur de l'OOS, **C** est le choix le plus prudent.
- Dans les deux cas : pas d'OOS pour 001-003, et pas de boucle « hypothèse → résultat → inverse ».

## 7. Décision : option C, campagne 001-003 terminée (2026-10-28)
**Conclusion de la campagne : sur cet univers de données, ces trois familles d'entrées ne fournissent pas une stratégie
suffisamment robuste pour justifier une validation hors échantillon.** Cela ne signifie pas que le forex est efficient ni
qu'aucune stratégie ne peut fonctionner : seulement que ce laboratoire n'a pas trouvé de candidat assez convaincant.

| Élément | État final |
|---|---|
| 001 Donchian | 6/6 REJECT |
| 002 Momentum en série temporelle | 6/6 REJECT |
| 003 Retour à la moyenne après séance extrême | 6/6 REJECT |
| Variantes testées (registre) | 18 |
| Candidats à l'OOS | 0 |
| OOS 2023-01-01 → 2026-10-27 | **intact**, jamais utilisé pour sélectionner une variante |
| Code, résultats, critères | figés |
| Expérience 004 | non préparée |

**Pourquoi s'arrêter plutôt que « trouver quelque chose »** : lancer une 004 parce que les trois premières familles ont
échoué reviendrait à choisir une idée suggérée par les résultats précédents, sur les mêmes données. Le laboratoire avait
le droit de conclure qu'il ne trouvait rien ; c'est ce résultat qui est retenu.

**Hypothèse future conservée, non testée** — *continuation à court terme* : « une séance exceptionnellement forte
annonce-t-elle une poursuite du mouvement sur quelques séances ? ». Elle est **dérivée de 003** (suggérée par son
résultat) et ne sera pas testée dans cette campagne. Si une campagne future la reprend, elle devra : être déclarée comme
dérivée de 003 ; avoir une hypothèse et une grille fixées avant tout code ; considérer que la validation 2020-2022 a déjà
informé l'idée ; et, de préférence, s'appuyer sur des données nouvelles ou indépendantes.

**Pour une campagne future indépendante** : l'OOS 2023-2026 est disponible, puisqu'il n'a servi à sélectionner aucune
variante de 001-003 (rappel : la famille « retour à la moyenne » avait été regardée informellement sur cette période
avant le laboratoire, journal 002 TradingView).
