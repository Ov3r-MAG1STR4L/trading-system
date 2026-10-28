"""
Backtest portefeuille sur les marchés de config/marches.csv (v0.3).

Lancement (aucune connexion MT5 : lit uniquement data/ et les fichiers de la v0.2) :
  python scripts/backtest.py

Le signal utilisé (strategies/exemple.py) est MÉCANIQUE : il sert à vérifier le moteur, pas à trader.
Sortie : reports/AAAA-MM-JJ_v0.3_portefeuille_exemple/ (voir src/rapport.py).
L'ancienne version monolithique de ce script reste dans l'historique Git (tag v0.2).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import couts, data, portefeuille, rapport  # noqa: E402
from src.engine import VERSION_MOTEUR, Params  # noqa: E402
from strategies import exemple  # noqa: E402

CAPITAL = 10_000
RISQUE_PCT = 0.01
TARGET_R = 2.0
SLIPPAGE_POINTS = 0.0
QUALITE = data.ROOT / "reports" / "2026-10-28_v0.2_donnees" / "qualite.csv"


def main():
    symboles = pd.read_csv(data.ROOT / "config" / "marches.csv", sep=";").query("actif == 1")["symbol"].tolist()
    marches = {s: data.charger(s) for s in symboles}
    infos = {s: couts.info_symbole(s) for s in symboles}
    # plancher de spread = médiane des spreads historiques NON NULS du marché sur la période (hypothèse déclarée).
    # Le spread « actuel » du relevé v0.2 n'est pas utilisable (GBPUSD -8, DE40 1000 : relevé marché fermé).
    planchers = {s: float(marches[s].loc[marches[s]["spread"] > 0, "spread"].median()) for s in symboles}
    hyp = {s: couts.Hypotheses("historique", planchers[s], SLIPPAGE_POINTS, swaps=True) for s in symboles}

    trades, ev = portefeuille.executer(marches, exemple.signaux, Params(TARGET_R), infos, hyp)
    debut = min(df["time"].min() for df in marches.values())
    fin = max(df["time"].max() for df in marches.values())
    dates = sorted(set().union(*(df["time"] for df in marches.values())))  # dates réelles de cotation
    a = portefeuille.analyser(trades, ev, symboles, CAPITAL, RISQUE_PCT, debut, dates)

    params = {"strategie": exemple.NOM, "params_strategie": {**exemple.PARAMS, "target_r": TARGET_R},
              "marches": symboles, "periode": {"debut": debut.date().isoformat(), "fin": fin.date().isoformat()},
              "source_donnees": "MT5 MetaQuotes-Demo, D1, data/*_D1.csv (v0.2)",
              "risque": {"capital": CAPITAL, "risque_pct": RISQUE_PCT, "compose": True,
                         "regle": "1 % du capital réalisé à l'entrée, risques simultanés additionnés, sans plafond"},
              "couts": {"spread_mode": "historique", "spread_points": "par marché : médiane des spreads historiques > 0",
                        "slippage_points": SLIPPAGE_POINTS, "swaps": True},
              "spread_plancher_points_par_marche": planchers,
              "date_swaps": str(infos[symboles[0]]["date_recuperation"]),
              "version_moteur": VERSION_MOTEUR}
    qualite = pd.read_csv(QUALITE, sep=";") if QUALITE.exists() else None
    dossier = rapport.ecrire("portefeuille_exemple", params, a["trades"], ev, qualite=qualite,
                             tables=a["tables"], portefeuille=a["resume"])

    print(a["tables"]["par_marche.csv"].to_string(index=False))
    print(f"\nRapport -> {dossier}")
    print((dossier / "avertissements.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
