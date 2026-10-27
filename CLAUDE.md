# CLAUDE.md — Règles du projet trading-system

Lis ce fichier, puis `STATUS.md`, `docs/ROADMAP.md` et `docs/decisions.md` avant toute action.

## Contexte
Projet de **recherche** en trading algorithmique (Python + MetaTrader 5, compte **démo**).
Utilisateur : étudiant ingénieur, débutant en finance, à l'aise en code. Réponds en français, tutoiement, phrases courtes.

## Règles non négociables

1. **Zéro trading réel.** N'écris, ne modifie et n'exécute aucun code qui envoie un ordre
   (`mt5.order_send`, `order_check` en vue d'un envoi, etc.), même sur compte démo,
   tant que `STATUS.md` n'indique pas l'étape « Paper trading » validée par l'utilisateur.
2. **Jamais de secret dans Git** : mot de passe, login de compte, token, clé API, `.env`.
   Vérifie `git status` / `git diff --staged` avant chaque commit.
3. **Le compte doit être en mode démo.** Tout script qui se connecte à MT5 doit pouvoir être
   précédé de `python scripts/check_env.py`. S'il signale un compte réel : stop, préviens l'utilisateur.
4. **Ne jamais décider seul** qu'une stratégie est rentable ou prête pour du réel.
5. **Ne jamais ajuster une stratégie, un backtest ou une conclusion pour rendre le projet plus vendeur.**
6. Interdits dans toute stratégie : martingale, moyenne à la baisse, augmentation de taille après une perte,
   déplacement/suppression du stop après l'entrée.

## Méthode expérimentale

- Chaque test = une hypothèse écrite **avant** le test, dans `docs/journal/NNN-nom.md` (modèle : `docs/journal/_modele.md`).
- Découpage entraînement / validation / hors échantillon fixé à l'avance. La période hors échantillon ne se regarde qu'une fois.
- Note le nombre de variantes essayées (risque de surapprentissage).
- Toute stratégie testée, même ratée, est enregistrée avec sa décision : Acceptée / À approfondir / Rejetée.
- Mets à jour `STATUS.md`, `docs/ROADMAP.md` et `docs/decisions.md` quand une étape avance.

## Backtests

- Résultats en **R** (multiples du risque), risque 1 % par trade.
- Signal à la clôture → entrée à l'ouverture suivante. Aucune donnée future.
- Stop et objectif dans la même bougie → compter le stop.
- Coûts : spread obligatoire ; ajouter swaps et slippage dès que possible (v0.3).
- Mesures à rapporter : trades, % gagnants, facteur de profit, espérance R, rendement, drawdown max,
  pire série de pertes, stabilité par marché et par période.
- Chaque exécution sauvegarde ses résultats dans `reports/AAAA-MM-JJ_vX.Y_nom/` avec les paramètres utilisés.

## Git

- Commits en anglais, explicites (« Add swap costs to backtest engine », pas « update »).
- Une évolution importante = un tag (`v0.1`, `v0.2`…), voir `docs/ROADMAP.md`.
- Demande avant : push, création de tag, suppression de fichier, réécriture d'historique.

## Environnement (Windows)

- Python 3.13 : `python` (pip via `python -m pip`)
- MetaTrader 5 : `C:\Program Files\MetaTrader 5\terminal64.exe` — doit être ouvert et connecté
- Commandes de base :
  - `python scripts/check_env.py`
  - `python scripts/lister_symboles.py`
  - `python scripts/backtest.py`

## Avant chaque proposition d'automatisation

Pose-toi la question : « Qu'est-ce qui pourrait faire perdre beaucoup d'argent si cette hypothèse est fausse ? »
Puis ajoute une protection ou un test qui détecte ce problème avant d'avancer.
