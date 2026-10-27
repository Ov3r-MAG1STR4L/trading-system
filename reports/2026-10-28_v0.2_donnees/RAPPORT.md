# Rapport v0.2 — Données (2026-10-28)

Source : MT5, serveur MetaQuotes-Demo (compte démo), bougies D1, heure serveur MT5.
Scripts : `scripts/telecharger_donnees.py`, `scripts/recuperer_swaps.py`. Paramètres : `params.json`.

## Conclusion

**v0.2 — DONNÉES : TERMINÉE**, avec les limitations listées plus bas.
Aucune donnée n'a été modifiée, interpolée ni supprimée.

## Période de référence

**2012-08-06 → 2026-10-27**, la période commune aux 12 marchés.
Les données antérieures restent dans `data/` à titre de référence, mais ne servent pas aux backtests de portefeuille.

## Résultats des contrôles (fichier `qualite.csv`)

| Contrôle | Résultat |
|---|---|
| Doublons, dates non triées, prix manquants ou ≤ 0 | 0 sur les 12 marchés |
| OHLC incohérents | 0 |
| Historique depuis 2012-08-06 | 12/12 (environ 3 600 bougies minimum) |
| Bougies plates (high = low) depuis 2012-08-06 | 0 à 0,28 % (DE40 : 10, US30 : 2, US500 : 1, AUDUSD : 1), sous le seuil de 0,5 % |
| Données à jour | dernière bougie au 2026-10-27 partout |

Avant 2012, le forex compte des milliers de bougies plates : séries reconstruites à partir du seul cours de clôture. On les conserve sans y toucher, en dehors de la période de référence.

## Trous de données dans la période de référence (fichier `trous.csv`)

| Marché | Dernière bougie avant | Première bougie après | Écart | Nature |
|---|---|---|---|---|
| US500 | 2025-07-16 | 2025-09-09 | 55 j | **trou du broker** |
| US30 | 2025-07-16 | 2025-09-09 | 55 j | **trou du broker** |
| DE40 | 2025-07-23 | 2025-09-09 | 48 j | **trou du broker** |
| DE40 | 2012-12-21, 2014-12-23, 2018-12-21, 2025-12-23 | +6 j | 6 j | fermeture de Noël (normal) |

Les trous restent tels quels. Le moteur v0.3 devra marquer ces périodes `DATA_GAP / NON_TRADABLE`.

## Événements extrêmes conservés (fichier `evenements_extremes.csv`)

Ce sont des rendements journaliers à plus de 12 écarts robustes de la médiane. Tous sont conservés :
- franc suisse (USDCHF, 2015-01-15, -13,5 %) ;
- Brexit (GBPUSD, 2016-06-24) ;
- Covid (indices, mars 2020) ;
- crise de 2008 (AUDUSD, XAUUSD) ;
- rebond du 2025-04-09 sur les indices.

**XAGUSD, 2026-01-30 (-31 % en log) et 2026-02-05 (-22 %)** : la série est cohérente d'un jour à l'autre (pic à 116,8 puis repli). **À vérifier avec une source indépendante** avant de tirer des conclusions sur cette série.

## Swaps (`../2026-10-28_v0.2_swaps/swaps.csv`, récupérés le 2026-10-28)

- Forex et métaux : en points par lot et par nuit, avec un **triple swap le mercredi**.
- Indices : en devise par lot, avec un **triple swap le vendredi**. US500 est en « devise de base », US30 et DE40 en « devise de marge ».
- Particularités : swaps positifs sur AUDUSD et NZDUSD long, USDCHF long et XAGUSD short ; tous les autres sont négatifs.
- **Limite majeure : MT5 ne fournit que les swaps actuels.** Les appliquer à 2012-2026 reste une approximation (taux proches de zéro jusqu'en 2021, puis hausse).
