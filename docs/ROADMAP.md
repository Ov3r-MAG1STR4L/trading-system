# Feuille de route

Chaque version correspond à un tag Git (`git tag v0.x`).

## v0.1 — Environnement *(terminée)*
- [x] Audit du PC (Python, Git, MT5, VS Code, TradingView)
- [x] Structure du dépôt, `.gitignore`, `.env.example`, `requirements.txt`
- [x] Règles de risque écrites
- [x] Journal des 3 premières expériences
- [x] `scripts/check_env.py` passe sans erreur
- [x] Premier commit + dépôt GitHub privé
- [x] Tag `v0.1`

## v0.2 — Données *(terminée le 2026-10-28)*
- [x] Inventaire des symboles (`lister_symboles.py`) → `config/marches.csv` (12 marchés)
- [x] Script de téléchargement des données historiques vers `data/` (CSV) — `telecharger_donnees.py`
- [x] Contrôles qualité : trous, doublons, bougies aberrantes, historique minimal (rapport 2026-10-28)
- [x] Traitement des anomalies décidé : période de référence 2012-08-06, trous conservés, extrêmes conservés
- [x] Récupération des swaps par symbole (`recuperer_swaps.py`, valeurs actuelles seulement)

## v0.3 — Moteur de backtest fiable *(terminée, auditée le 2026-10-28, tag à créer)*
- [x] Premier backtest multi-paires (version script unique)
- [x] Extraire indicateurs et moteur dans `src/`
- [x] Tests automatiques : pas de look-ahead, calcul du R, gestion stop/objectif
- [x] Trous de données (`reports/…_v0.2_donnees/trous.csv`) → statut `DATA_GAP / NON_TRADABLE`. Tests : un trou n'est **jamais** traité comme un prix inchangé, un rendement nul, une bougie créée ou une période tradable ; aucune entrée ni sortie normale pendant le trou
- [x] Backtests de portefeuille limités à la période de référence 2012-08-06 → aujourd'hui
- [x] Ajouter slippage et swaps
- [x] Chaque exécution enregistre ses paramètres + la version Git dans `reports/`

- [x] Portefeuille 12 marchés : allocation, exposition, equity réalisée (`src/portefeuille.py`)
- [x] Audit technique ([`docs/audit-v0.3.md`](audit-v0.3.md)) : 174 tests
- [ ] Décider : plafond d'exposition (risque ouvert max 11 % observé), swaps des indices (`SWAP_UNAVAILABLE`)

## v0.4 — Stratégie de suivi de tendance diversifiée
- [ ] Hypothèse écrite avant le test
- [ ] Portefeuille multi-marchés (forex, indices, matières premières)

## v0.5 — Validation hors échantillon
- [ ] Découpage entraînement / validation / test fixé à l'avance
- [ ] Walk-forward
- [ ] Sensibilité aux paramètres

## Plus tard (conditionnel)
- Paper trading sur démo, surveillance, automatisation limitée.
- Contenu pédagogique, **seulement** à partir de résultats réels documentés.
