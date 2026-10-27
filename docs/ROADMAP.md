# Feuille de route

Chaque version correspond à un tag Git (`git tag v0.x`).

## v0.1 — Environnement *(en cours)*
- [x] Audit du PC (Python, Git, MT5, VS Code, TradingView)
- [x] Structure du dépôt, `.gitignore`, `.env.example`, `requirements.txt`
- [x] Règles de risque écrites
- [x] Journal des 3 premières expériences
- [x] `scripts/check_env.py` passe sans erreur
- [ ] Premier commit + dépôt GitHub privé
- [ ] Tag `v0.1`

## v0.2 — Données
- [ ] Inventaire des symboles (`lister_symboles.py`) → `config/marches.csv`
- [ ] Script de téléchargement des données historiques vers `data/` (format Parquet ou CSV)
- [ ] Contrôles qualité : trous, doublons, bougies aberrantes, historique minimal
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
