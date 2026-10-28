"""Non-régression : le moteur actuel (options retournement et duree_max comprises) reproduit À L'IDENTIQUE les trades
commités des expériences 001 et 002. Lecture seule : aucun rapport écrit, aucune expérience rejouée, données
d'ENTRAÎNEMENT seulement (tronquées à 2019-12-31 par recherche.evaluer), OOS jamais lu."""
import pandas as pd
import pytest

from src import couts, data
from src import recherche as rc
from strategies import donchian, momentum

COLONNES = ["direction", "entry_time", "entry", "stop", "dist", "exit_time", "exit", "raison", "bougies", "R",
            "traverse_gap", "R_execution", "nuits_swap", "swap_R", "R_net"]
CAS = [("001-donchian-baseline", "N20_S2", donchian.variante({"n": 20, "stop_atr": 2.0})),
       ("002-momentum-serie-temporelle", "L60_K3", momentum.variante({"L": 60, "k": 3.0}))]
SYMBOLE = "EURUSD"  # les trades d'un marché ne dépendent pas des autres marchés


@pytest.mark.skipif(not (data.DATA_DIR / f"{SYMBOLE}_D1.csv").exists(), reason="données v0.2 absentes")
@pytest.mark.parametrize("dossier,variante,strategie", CAS)
def test_trades_commites_reproduits_a_l_identique(dossier, variante, strategie):
    rapport = next((rc.EXPERIMENTS / dossier / "rapports").glob(f"*_{variante}_entrainement"))
    attendu = pd.read_csv(rapport / "resultats.csv", sep=";", parse_dates=["entry_time", "exit_time"])
    attendu = attendu[attendu["symbol"] == SYMBOLE].reset_index(drop=True)

    df = data.charger(SYMBOLE)
    fin_val = pd.Timestamp(rc.PERIODES["validation"][1])
    plancher = float(df.loc[(df["time"] <= fin_val) & (df["spread"] > 0), "spread"].median())  # comme 001 et 002
    hyp = {SYMBOLE: couts.Hypotheses("historique", plancher, 0.0)}
    ev = rc.evaluer({SYMBOLE: df}, strategie, {SYMBOLE: couts.info_symbole(SYMBOLE)}, hyp, "entrainement")
    obtenu = ev["trades"].reset_index(drop=True)

    assert len(obtenu) == len(attendu) > 20
    assert not obtenu["retournement"].any() if variante.startswith("N") else obtenu["retournement"].any()
    assert "duree" not in set(obtenu["raison"])
    pd.testing.assert_frame_equal(obtenu[COLONNES], attendu[COLONNES], check_dtype=False, rtol=0, atol=1e-12)
