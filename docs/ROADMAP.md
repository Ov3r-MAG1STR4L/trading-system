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

## v0.2 — Données *(en cours)*
- [x] Inventaire des symboles (`lister_symboles.py`) → `config/marches.csv` (12 marchés)
- [x] Script de téléchargement des données historiques vers `data/` (CSV) — `telecharger_donnees.py`
- [x] Contrôles qualité : trous, doublons, bougies aberrantes, historique minimal (rapport 2026-10-28)
- [ ] Décider du traitement des anomalies (trou indices 2025, forex reconstruit avant 2012)
- [ ] Récupération des swaps par symbole

## v0.3 — Moteur de backtest fiable
- [x] Premier backtest multi-paires (version script unique)
- [ ] Extraire indicateurs et moteur dans `src/`
- [ ] Tests automatiques : pas de look-ahead, calcul du R, gestion stop/objectif
- [ ] Ajouter slippage et swaps
- [ ] Chaque exécution enregistre ses paramètres + la version Git dans `reports/`

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
