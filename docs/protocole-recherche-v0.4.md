# Protocole de recherche v0.4 — VALIDÉ le 2026-10-28

But : décider si une idée mérite des tests supplémentaires, pas trouver le meilleur backtest.
Question à laquelle chaque expérience répond :
**« Cette idée fonctionne-t-elle hors échantillon, après coûts, avec un risque raisonnable, sur plusieurs marchés ? »**

## 1. Découpage temporel (fixé AVANT toute expérience, jamais modifié)

| Période | Dates | Durée | Usage |
|---|---|---|---|
| Entraînement | 2012-08-06 → 2019-12-31 | ~7,4 ans | choix des paramètres dans la grille autorisée |
| Validation | 2020-01-01 → 2022-12-31 | 3 ans | confirmation ; **aucun réglage** après l'avoir vue |
| Hors échantillon (OOS) | 2023-01-01 → 2026-10-27 | ~3,8 ans | **regardée une seule fois** par stratégie retenue |

- Les indicateurs ont besoin d'historique : la période de chauffe est prise AVANT le début de chaque fenêtre ;
  les signaux de chauffe ne tradent pas.
- Les trades à cheval sur deux périodes sont attribués à leur **date d'entrée**.
- L'OOS contient le trou des indices de l'été 2025 : il est traité par la règle DATA_GAP, pas exclu.
- Toute ouverture de l'OOS est enregistrée dans l'expérience (date, commit). Une deuxième ouverture = l'OOS est « brûlé »
  pour cette famille de stratégies.

## 2. Budget de variantes (surapprentissage)

- Par famille de stratégies : **au plus 3 paramètres libres**, chacun avec **au plus 3 valeurs fixées à l'avance**
  (donc ≤ 27 variantes), écrites dans l'hypothèse AVANT le test.
- Compteur global des variantes testées depuis le début du projet, enregistré dans chaque expérience.
- Pas de grid search fin, pas d'ajout de filtre après avoir vu un résultat sans ouvrir une NOUVELLE expérience
  (qui consomme son propre budget).
- Choix sur l'entraînement : la variante retenue doit être entourée de voisines qui restent positives
  (plateau), sinon REJECT (pic isolé = probable hasard).

## 3. Coûts obligatoires

- Spread : plancher par marché = médiane des spreads > 0 (hypothèse v0.3, déclarée).
- Slippage : **scénario de base 0** et **scénario de stress = 1 × plancher de spread par exécution** ; une stratégie n'est
  conservée que si elle reste positive dans le scénario de stress.
- Swaps : forex et métaux (mode points) ; indices US500, US30, DE40 convertis car devise du swap = devise du profit
  en calcul CFD (vérifié dans MT5, relevé `reports/2026-10-28_v0.4_swaps/`) ; sinon `SWAP_UNAVAILABLE`, jamais 0.
  Swaps ACTUELS appliqués à tout l'historique : approximation déclarée. Les trois niveaux sont TOUJOURS rapportés :
  brut, après spread/slippage, net (ou `SWAP_UNAVAILABLE`).
- Critère de décision sur **R après spread + slippage** (et net quand il est calculable), jamais sur le brut.

## 4. Risque et drawdown

- Évaluation principale **en R** (indépendante du dimensionnement).
- Portefeuille : **0,25 % du capital réalisé par trade, sans plafond d'exposition** (décision 1) : tous les trades de la
  stratégie sont conservés, l'exposition simultanée est mesurée et rapportée. Le plafond de 3 % reste une règle de
  sécurité pour une future couche d'exécution, il ne supprime aucun trade en recherche ; drawdown rapporté = `drawdown_realise`
  (limite : pertes latentes non comptées).
- Seuil de rejet : drawdown réalisé > 25 % au risque de référence, ou pire série de pertes > 20 trades.

## 5. Critères

**Nombre minimal de trades** : ≥ 150 sur le portefeuille en entraînement, ≥ 60 en validation ; un marché avec < 15 trades
n'entre pas dans les statistiques de stabilité par marché.

**REJECT** (un seul suffit, sur validation après coûts) :
- espérance ≤ 0 R, ou profit factor < 1,10 ;
- négative dans le scénario de stress (slippage) ;
- positive sur moins de 7 marchés sur 12 ;
- un seul marché fait plus de 40 % du gain total ;
- moins de 60 % des années civiles positives (entraînement + validation) ;
- ne bat pas le benchmark (section 6) ;
- variante isolée (pas de plateau, section 2).

**NEEDS_REVIEW** : passe les critères de rejet mais avec un indicateur limite (marge < 10 % d'un seuil), ou résultat
dépendant d'un événement unique (une année/un krach fait la majorité du gain).

**KEEP** (candidat à l'OOS, PAS une preuve de rentabilité) : aucun critère de rejet en entraînement ET en validation.
Après l'OOS unique : KEEP si espérance après coûts > 0 et profit factor ≥ 1,05 en OOS, sinon REJECT.
KEEP signifie seulement « mérite d'autres tests » (walk-forward, autres marchés, paper trading).

## 6. Benchmarks

1. **Entrées aléatoires** : mêmes marchés, même nombre de trades par marché, même règle de stop/objectif/sortie,
   directions et dates tirées au hasard (graines fixes, 200 tirages). La stratégie doit dépasser le **95e centile** de
   l'espérance après coûts des tirages.
2. **Achat-conservation** à risque égal (référence de « marché haussier »), rapporté pour information.

## 7. Traçabilité

Chaque expérience vit dans `experiments/NNN-nom/` (proposition) :
- `hypothese.md` : écrit AVANT le test (idée, grille, critères ; modèle `docs/journal/_modele.md`) ;
- `experience.json` : identifiant, stratégie, grille, marchés, périodes, coûts, commit, compteur de variantes ;
- un rapport par période (`rapport.py`) ;
- `decision.json` : `KEEP / REJECT / NEEDS_REVIEW` + raison + critères chiffrés + date d'ouverture de l'OOS.
Les expériences rejetées restent dans le dépôt.

## 8. Première expérience proposée (baseline, pas une stratégie définitive)

Breakout de Donchian : entrée si clôture > plus haut des N jours (short si < plus bas), stop 2 × ATR(20),
sortie sur clôture inverse au plus bas/haut des N/2 jours, pas d'objectif.
Grille fixée à l'avance : N ∈ {20, 55, 100}, stop ∈ {2, 3} × ATR → 6 variantes. Mêmes 12 marchés, même protocole.
