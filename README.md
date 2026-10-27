# trading-system

Projet personnel de **recherche en trading algorithmique** avec Python et MetaTrader 5.

> ⚠️ **Trading réel : INTERDIT** à ce stade. Voir [`STATUS.md`](STATUS.md).
> Ce dépôt ne contient aucun conseil financier et aucune promesse de gain.

## Objectif

Construire, étape par étape, un environnement capable de :

1. récupérer des données historiques (MT5, compte **démo**) ;
2. tester des stratégies comme des **hypothèses** (backtest) ;
3. valider hors échantillon ;
4. documenter chaque expérience, y compris les échecs ;
5. **seulement ensuite**, envisager du paper trading puis une automatisation limitée.

Progression imposée (aucune étape ne peut être sautée) :

```
Recherche → Données → Backtest → Analyse statistique → Validation hors échantillon
→ Paper trading (démo) → Surveillance → Automatisation limitée → (éventuellement) très petit capital réel
```

## Priorités

1. Exactitude
2. Sécurité
3. Reproductibilité
4. Documentation
5. Performance
6. Éventuellement monétisation (contenu pédagogique) — **ne doit jamais influencer les résultats**

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `scripts/` | Scripts exécutables (découverte des symboles, backtests, vérification de l'environnement) |
| `src/` | Code réutilisable (indicateurs, moteur de backtest) — à extraire des scripts au fil du projet |
| `strategies/` | Définition des stratégies (`pine/` pour les versions TradingView) |
| `config/` | Paramètres (marchés, règles de risque) — **sans secret** |
| `data/` | Données téléchargées — **jamais versionnées** |
| `reports/` | Résultats de chaque expérience, datés et liés à une version |
| `tests/` | Tests automatiques (anti look-ahead, cohérence des calculs) |
| `docs/` | Journal des expériences, décisions, règles de risque, feuille de route |

## Démarrage

Prérequis : Windows, Python 3.13, MetaTrader 5 ouvert et connecté à un **compte démo**.

```bash
python -m pip install -r requirements.txt
python scripts/check_env.py        # vérifie Python, paquets, connexion MT5 et compte DÉMO
python scripts/lister_symboles.py  # inventaire des marchés disponibles chez le broker
python scripts/backtest.py         # backtest multi-paires (v0.3)
```

## Sécurité

- Aucun mot de passe, token, clé API ou identifiant de compte dans le dépôt.
- Le fichier `.env` est exclu par `.gitignore` ; seul `.env.example` (vide de secrets) est versionné.
- Les scripts refusent de tourner sur un compte qui n'est pas en mode **démo**.
- Règles de risque : [`docs/regles-de-risque.md`](docs/regles-de-risque.md).

## Documentation

- État actuel : [`STATUS.md`](STATUS.md)
- Feuille de route : [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Journal des expériences : [`docs/journal/`](docs/journal/)
- Décisions : [`docs/decisions.md`](docs/decisions.md)
