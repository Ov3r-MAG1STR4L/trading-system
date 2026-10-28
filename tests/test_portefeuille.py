import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src import portefeuille as pf
from src import rapport
from src.couts import SWAP_UNAVAILABLE, Hypotheses
from src.engine import VERSION_MOTEUR, Params
from tests.outils import PLAT, bougies

CAP, PCT = 10_000, 0.01
J = pd.Timestamp("2020-01-06")  # lundi
INFO = {"symbol": "X", "swap_long": -2.0, "swap_short": 1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}


def d(k):
    return J + pd.Timedelta(days=k)


def table(lignes):
    """lignes : (symbole, jour d'entrée, jour de sortie, R) -> table de trades minimale, coûts nuls."""
    t = pd.DataFrame([{"symbol": s, "entry_time": d(e), "exit_time": d(x), "R": r, "R_execution": r, "R_net": r,
                       "statut_swap": "OK", "cout_spread_R": 0.0, "cout_slippage_R": 0.0, "swap_R": 0.0,
                       "traverse_gap": False} for s, e, x, r in lignes])
    return t


def analyser(t, marches=("A", "B", "C", "D")):
    return pf.analyser(t, pd.DataFrame(columns=["symbol", "entree_refusee"]), list(marches), CAP, PCT, J)


# ---------------- test de référence A +2, B -1, C -1, D +3 ----------------

def test_reference_trades_successifs_capital_compose():
    a = analyser(table([("A", 0, 1, 2), ("B", 2, 3, -1), ("C", 4, 5, -1), ("D", 6, 7, 3)]))
    alloc = a["allocations"]["brut"]
    assert alloc["risque_initial"].tolist() == pytest.approx([100, 102, 100.98, 99.9702])
    assert alloc["pnl"].tolist() == pytest.approx([200, -102, -100.98, 299.9106])
    eq = a["tables"]["equity.csv"]["equity_brut_realisee"].tolist()
    assert eq == pytest.approx([10_000, 10_200, 10_098, 9_997.02, 10_296.9306])
    r = a["resume"]["brut"]
    assert r["capital_final"] == pytest.approx(10_296.9306)
    assert r["drawdown_realise"] == pytest.approx(202.98) and r["drawdown_realise_pct"] == pytest.approx(0.0199)
    pm = a["tables"]["par_marche.csv"].set_index("symbol")
    assert pm["R_brut"].tolist() == [2, -1, -1, 3]
    assert pm["pnl_brut"].sum() == pytest.approx(296.9306)
    assert pm["contribution_pnl_brut"].sum() == pytest.approx(1)


def test_reference_positions_simultanees_risques_additionnes():
    a = analyser(table([("A", 0, 1, 2), ("B", 0, 2, -1), ("C", 0, 3, -1), ("D", 0, 4, 3)]))
    alloc = a["allocations"]["brut"]
    assert alloc["risque_initial"].tolist() == pytest.approx([100] * 4)  # tous dimensionnés sur 10 000
    assert a["resume"]["brut"]["capital_final"] == pytest.approx(10_300)
    x = a["resume"]["exposition"]
    assert x["positions_simultanees_max"] == 4
    assert x["risque_ouvert_max"] == pytest.approx(400) and x["risque_ouvert_max_pct"] == pytest.approx(0.04)


def test_deux_positions_simultanees_risques_non_ecrases():
    a = analyser(table([("A", 0, 7, 1), ("B", 1, 3, -1)]), ("A", "B"))
    alloc = a["allocations"]["brut"]
    assert alloc["risque_initial"].tolist() == pytest.approx([100, 100])  # A pas encore sorti à l'entrée de B
    expo = a["tables"]["exposition.csv"]
    assert expo["positions_ouvertes"].tolist() == [1, 2]
    assert expo["risque_ouvert"].tolist() == pytest.approx([100, 200])
    assert expo["marches_ouverts"].iloc[1] == "A,B"


def test_capital_a_l_entree_n_inclut_que_les_sorties_strictement_anterieures():
    a = analyser(table([("A", 0, 2, 2), ("B", 2, 4, 1), ("C", 3, 5, 1)]), ("A", "B", "C"))
    risq = a["allocations"]["brut"]["risque_initial"].tolist()
    assert risq == pytest.approx([100, 100, 102])  # B entre le jour de la sortie de A : pas encore compté


def test_pas_de_risque_multiplie_par_le_nombre_de_marches():
    a = analyser(table([("A", 0, 1, -1)]), ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"))
    assert a["resume"]["exposition"]["risque_ouvert_max_pct"] == pytest.approx(0.01)
    assert a["resume"]["brut"]["capital_final"] == pytest.approx(9_900)


def test_aucun_trade():
    a = analyser(table([]).reindex(columns=table([("A", 0, 1, 1)]).columns))
    assert a["resume"]["brut"]["capital_final"] == CAP
    assert a["resume"]["exposition"]["positions_simultanees_max"] == 0


# ---------------- coûts et SWAP_UNAVAILABLE ----------------

def test_brut_execution_net_separes():
    t = table([("A", 0, 1, 2), ("B", 2, 3, -1)])
    t["R_execution"] = [1.9, -1.1]
    t["R_net"] = [1.85, -1.12]
    r = analyser(t, ("A", "B"))["resume"]
    assert r["brut"]["capital_final"] > r["execution"]["capital_final"] > r["net"]["capital_final"]


def test_swap_unavailable_propage_sans_zero():
    t = table([("A", 0, 1, 2), ("IDX", 2, 3, -1), ("C", 4, 5, 1)])
    t.loc[1, ["swap_R", "R_net", "statut_swap"]] = [np.nan, np.nan, SWAP_UNAVAILABLE]
    a = analyser(t, ("A", "IDX", "C"))
    eq = a["tables"]["equity.csv"]
    assert eq["equity_net_realisee"].iloc[1] == pytest.approx(10_200)   # avant : connu
    assert eq["equity_net_realisee"].iloc[2:].isna().all()               # après : inconnu, pas complété
    assert eq["equity_brut_realisee"].notna().all()                      # le brut reste calculable
    r = a["resume"]
    assert r["net"]["capital_final"] is None and r["net"]["statut"] == SWAP_UNAVAILABLE
    assert r["marches_swap_unavailable"] == ["IDX"]
    pm = a["tables"]["par_marche.csv"].set_index("symbol")
    assert pm.loc["IDX", "R_net"] == SWAP_UNAVAILABLE and pm.loc["A", "R_net"] == 2


# ---------------- pipeline complet sur bougies synthétiques ----------------

def marche(n, seed, debut="2020-01-06"):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)), debut=debut)
    df["spread"] = 20
    return df


def strat(df):
    m = df["close"].rolling(5).mean()
    return {"signal": np.sign(df["close"] - m).diff().fillna(0).clip(-1, 1),
            "stop_dist": (df["high"] - df["low"]).rolling(5).mean()}


def lancer(marches, infos=None, h=Hypotheses("fixe", 20, 2)):
    infos = infos or {s: {**INFO, "symbol": s} for s in marches}
    return pf.executer(marches, strat, Params(2.0), infos, h)


def test_marches_avec_dates_differentes_restent_synchronises_par_date():
    a = marche(150, 1)
    b = marche(140, 2, debut="2020-01-20")
    b = b.drop(index=range(30, 35)).reset_index(drop=True)  # B ne cote pas 5 jours (fériés locaux)
    trades, ev = lancer({"A": a, "B": b})
    for sym, df in (("A", a), ("B", b)):
        t = trades[trades["symbol"] == sym]
        assert set(t["entry_time"]) <= set(df["time"]) and set(t["exit_time"]) <= set(df["time"])
    assert trades["entry_time"].is_monotonic_increasing  # agrégé dans l'ordre chronologique réel
    assert len(a) == 150 and len(b) == 135  # aucune bougie ajoutée


def test_data_gap_sur_un_seul_marche_l_autre_continue():
    ohlc = [PLAT] * 12
    a = bougies(ohlc, gaps_avant=(6,))
    b = bougies(ohlc)
    sig = pd.Series(0.0, index=range(12))
    sig[2] = 1

    def s(df):
        return {"signal": sig, "stop_dist": pd.Series(5.0, index=range(12))}
    infos = {k: {**INFO, "symbol": k} for k in "AB"}
    trades, ev = pf.executer({"A": a, "B": b}, s, Params(2.0), infos, Hypotheses("fixe", 0, 0))
    t = trades.set_index("symbol")
    assert t.loc["A", "traverse_gap"] and not t.loc["B", "traverse_gap"]
    assert ev["symbol"].tolist() == ["A"]
    assert t.loc["A", "raison"] == t.loc["B", "raison"] == "fin_donnees"  # A n'est pas coupé par le trou


def test_pipeline_swap_unavailable_sur_un_marche():
    infos = {"A": {**INFO, "symbol": "A"}, "IDX": {**INFO, "symbol": "IDX", "swap_mode": 3}}
    trades, ev = lancer({"A": marche(200, 1), "IDX": marche(200, 2)}, infos)
    idx = trades[trades["symbol"] == "IDX"]
    nuit = idx["nuits_swap"] > 0
    assert nuit.any() and (idx.loc[nuit, "statut_swap"] == SWAP_UNAVAILABLE).all()
    assert idx.loc[nuit, "R_net"].isna().all()
    assert trades.loc[trades["symbol"] == "A", "R_net"].notna().all()


def test_modifier_le_futur_d_un_marche_ne_change_pas_les_decisions_passees():
    a, b = marche(200, 1), marche(200, 2)
    coupure = a["time"][120]
    t1, _ = lancer({"A": a, "B": b})
    b2 = b.copy()
    b2.loc[121:, ["open", "high", "low", "close"]] *= 1.5
    t2, _ = lancer({"A": a, "B": b2})
    al1 = pf.allouer(t1, CAP, PCT)
    al2 = pf.allouer(t2, CAP, PCT)
    passe1, passe2 = t1["exit_time"] <= coupure, t2["exit_time"] <= coupure
    assert passe1.sum() > 5
    pd.testing.assert_frame_equal(t1[passe1].reset_index(drop=True), t2[passe2].reset_index(drop=True))
    pd.testing.assert_frame_equal(al1[passe1].reset_index(drop=True), al2[passe2].reset_index(drop=True))
    # et les trades de A, même après la coupure, ne dépendent pas de B
    pd.testing.assert_frame_equal(t1[t1["symbol"] == "A"].reset_index(drop=True),
                                  t2[t2["symbol"] == "A"].reset_index(drop=True))


# ---------------- rapport portefeuille ----------------

def test_rapport_portefeuille_complet(tmp_path):
    trades, ev = lancer({"A": marche(200, 1), "B": marche(200, 2)})
    a = pf.analyser(trades, ev, ["A", "B"], CAP, PCT, "2020-01-06")
    params = {"strategie": "test", "params_strategie": {}, "marches": ["A", "B"],
              "periode": {"debut": "2020-01-06", "fin": "2020-10-01"}, "source_donnees": "synthétique",
              "risque": {"capital": CAP, "risque_pct": PCT, "compose": True},
              "couts": Hypotheses("fixe", 20, 2).en_dict(), "version_moteur": VERSION_MOTEUR}
    dos = rapport.ecrire("pf", params, a["trades"], ev, racine=tmp_path, git={"commit": "a" * 40, "dirty": False},
                         maintenant=datetime(2026, 10, 28), tables=a["tables"], portefeuille=a["resume"])
    for f in ("equity.csv", "exposition.csv", "par_marche.csv", "allocation_brut.csv", "resultats.csv"):
        assert (dos / f).exists(), f
    res = json.loads((dos / "resume.json").read_text("utf-8"))
    assert "drawdown_realise" in res["portefeuille"]["brut"]
    assert "drawdown_max" not in res["brut"]  # pas d'equity séquentielle trompeuse
    r = pd.read_csv(dos / "resultats.csv", sep=";")
    assert {"symbol", "risque_initial", "pnl_brut", "pnl_net", "traverse_gap", "statut_swap"} <= set(r.columns)
    av = (dos / "avertissements.txt").read_text("utf-8")
    assert "DRAWDOWN : calculé sur l'equity RÉALISÉE" in av and "RISQUE SIMULTANÉ" in av
