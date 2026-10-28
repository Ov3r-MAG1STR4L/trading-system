# Audit technique v0.3 (2026-10-28)

Revue du moteur avant la v0.4. Aucune stratégie développée. Rapport de référence :
[`reports/2026-10-28_v0.3_portefeuille_exemple/`](../reports/2026-10-28_v0.3_portefeuille_exemple/)
(signal mécanique `strategies/exemple.py`, à ne pas interpréter).

## Bugs trouvés et corrigés

| # | Bug | Impact | Test qui le reproduit |
|---|---|---|---|
| 1 | Une entrée refusée par un DATA_GAP n'était pas journalisée si la position ouverte sortait sur la bougie de reprise (refus calculé avant la sortie). | Compteur `entrees_refusees` sous-estimé. Trades inchangés. 0 cas sur les 12 marchés. | `test_bug_refus_journalise_si_la_position_sort_a_la_reprise` |
| 2 | Capital ≤ 0 (perte > 100 R) : `allouer` plantait. | Pas de rapport possible en cas de ruine. Désormais état `RUINE`, puis `CAPITAL_INCONNU`. 0 cas réel. | `test_ruine_etat_explicite_sans_plantage` |
| 3 | `drawdown_realise` affichait le statut `SWAP_UNAVAILABLE` même quand l'equity était inconnue à cause d'une ruine ; le rapport mono-marché nommait `drawdown_max` un drawdown réalisé. | Libellés trompeurs, valeurs inchangées. Désormais `EQUITY_INCONNUE` et `drawdown_realise` partout. | tests de `test_rapport.py` / `test_portefeuille.py` |
| 4 | `etat_git` comptait les fichiers NON SUIVIS (rapports fraîchement créés) comme « dirty ». | Fausse alerte Git. Corrigé à l'étape portefeuille. | `test_fichier_non_suivi_ne_rend_pas_dirty` |

Non-régression : trades, résultats par marché, equity et journal des trous **identiques à l'octet** au rapport
d'avant l'audit (`..._3`). Deux exécutions consécutives : tous les fichiers identiques sauf l'horodatage de `params.json`.

## Anti-look-ahead

Garanti par construction et testé :
- le moteur lit `signal[i-1]`, `stop_dist[i-1]`, `sortie[i-1]` à la bougie i ; entrée et sortie sur signal à `open[i]` ;
- indicateurs causaux (`ewm(adjust=False)`, `shift()`) ;
- allocation : capital = sorties **strictement** antérieures à l'entrée ;
- marchés backtestés séparément : un marché ne lit jamais les bougies d'un autre.

Tests : stratégie tricheuse détectée ; futur modifié ×10, inversé, bruité sur **tous** les marchés -> signaux, entrées,
sorties et allocations avant T identiques ; futur d'un marché sans effet sur un autre.

Fuites de **coûts** (pas de décisions), laissées et déclarées :
- le plancher de spread = médiane des spreads > 0 sur toute la période (paramètre non causal) ;
- le spread D1 de MT5 est lu sur la bougie d'entrée alors que sa définition exacte (min, ouverture ?) n'est pas documentée.

## Unités des 12 marchés

Les résultats sont en **R** (rapport de distances de prix) : ni taille de lot ni taux de change ne sont nécessaires.
Le montant en euros = R × risque en euros (1 % du capital) : il n'utilise pas non plus la valeur du point.
La **taille de position** en lots n'est PAS calculée (nécessiterait la valeur du point historique en EUR).

| Symbole | Type | Prix coté en | Point | Contrat (unités/lot) | Valeur tick (EUR/lot) * | Spread | Swap | Devise du swap | Conversion nécessaire ? | Conversion disponible ? |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | forex | USD | 1e-05 | 100000 | 0.8985 | points × 1e-05 | points/lot/nuit | sans objet (converti en prix) | en R : non ; en lots : oui | lots : non |
| GBPUSD | forex | USD | 1e-05 | 100000 | 0.8985 | points × 1e-05 | points/lot/nuit | sans objet | idem | lots : non |
| USDJPY | forex | JPY | 0.001 | 100000 | 0.5688 | points × 0.001 | points/lot/nuit | sans objet | idem | lots : non |
| USDCHF | forex | CHF | 1e-05 | 100000 | 1.084 | points × 1e-05 | points/lot/nuit | sans objet | idem | lots : non |
| USDCAD | forex | CAD | 1e-05 | 100000 | 0.6396 | points × 1e-05 | points/lot/nuit | sans objet | idem | lots : non |
| AUDUSD | forex | USD | 1e-05 | 100000 | 0.8985 | points × 1e-05 | points/lot/nuit | sans objet | idem | lots : non |
| NZDUSD | forex | USD | 1e-05 | 100000 | 0.8985 | points × 1e-05 | points/lot/nuit | sans objet | idem | lots : non |
| US500 | indice | USD | 0.01 | 1 | 0.008985 | points × 0.01 | devise de base / lot | **INCONNUE** | swap : oui | **non** -> `SWAP_UNAVAILABLE` |
| US30 | indice | USD | 0.01 | 1 | 0.008985 | points × 0.01 | devise de marge / lot | **INCONNUE** | swap : oui | **non** -> `SWAP_UNAVAILABLE` |
| DE40 | indice | EUR | 0.01 | 1 | 0.01 | points × 0.01 | devise de marge / lot | **INCONNUE** | swap : oui | **non** -> `SWAP_UNAVAILABLE` |
| XAUUSD | métal | USD | 0.01 | 100 | 0.1 | points × 0.01 | points/lot/nuit | sans objet | en R : non ; en lots : oui | lots : non |
| XAGUSD | métal | USD | 0.001 | 5000 | 0.5 | points × 0.001 | points/lot/nuit | sans objet | idem | lots : non |

\* valeur au 2026-10-28 seulement (dépend du taux de change du jour) : inutilisable pour l'historique.
Slippage : en **points du marché** (donc à fixer par marché comme le spread). Aucun pip n'est utilisé dans le code.
Devise de base / de marge des indices : non relevée en v0.2 ; un relevé MT5 (`currency_base`, `currency_margin`)
plus un taux de change historique seraient nécessaires.

## Exposition (signal d'exemple, 12 marchés, 3 698 jours)

- Positions simultanées max : **11** ; risque ouvert max : **1 498,64 €, soit 11,0 %** (le 2026-03-27).
- Distribution du risque ouvert : médiane 4,1 % ; 75e centile 6,0 % ; 90e 7,9 % ; 95e 8,9 % ; 99e 10,1 %.
- Jours strictement au-dessus du seuil (part des jours, plus longue période consécutive) :

| Seuil | Jours | Part | Plus longue période |
|---|---|---|---|
| 2 % | 3 132 | 84,7 % | 259 jours |
| 3 % | 2 666 | 72,1 % | 190 jours |
| 5 % | 1 433 | 38,8 % | 82 jours |
| 8 % | 346 | 9,4 % | 31 jours |
| 10 % | 49 | 1,3 % | 12 jours |

- Marchés présents les jours > 5 % : tous, entre 640 (DE40) et 916 (NZDUSD) jours -> l'exposition vient du nombre de
  marchés ouverts en même temps, pas d'un marché isolé.
- La règle prévue dans `docs/regles-de-risque.md` (risque total ouvert ≤ 3 %) serait dépassée 72 % du temps.
  **Aucun plafond ajouté** : décision à prendre explicitement.

## Problèmes laissés volontairement

1. Pas de mark-to-market : drawdown **réalisé** seulement (`drawdown_realise`), le vrai drawdown peut être plus grand.
2. Pas de plafond d'exposition ni de nombre de positions (mesuré, non limité).
3. Stops déclenchés sur le BID (un short réel sort plus tôt, sur l'ask).
4. Stop prioritaire même si l'ouverture dépasse l'objectif puis le prix revient au stop (règle prudente du projet).
5. Net inconnu dès qu'un indice passe une nuit (`SWAP_UNAVAILABLE`) : net du portefeuille inconnu dès 2012-11.
6. Chemins de fichiers v0.2 datés codés en dur (`trous.csv`, `swaps.csv`) dans `data.py` / `couts.py`.
7. Spread historique MT5 peu fiable (beaucoup de 0) ; spread « actuel » du relevé v0.2 aberrant (GBPUSD -8, DE40 1000).
8. Une seule source de données ; swaps actuels appliqués au passé.
