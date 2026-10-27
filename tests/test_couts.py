import math

import numpy as np
import pandas as pd
import pytest

from src import couts
from src.couts import CoutInvalide, Hypotheses, appliquer, nuits_swap, prix_execution

# point = 0.01 ; spread 50 points = 0.50 de prix ; slippage 10 points = 0.10 ; risque initial dist = 5
INFO = {"symbol": "TEST", "swap_long": -2.0, "swap_short": 1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}
LUN = pd.Timestamp("2020-01-06")  # un lundi
SANS_COUT = Hypotheses("fixe", 0, 0, swaps=False)


def jour(k):
    return LUN + pd.Timedelta(days=k)


def bougies(spread=50, jours=14):
    return pd.DataFrame({"time": [jour(k) for k in range(jours)], "spread": spread})


def trade(direction="long", entry=100.0, exit=110.0, e=0, s=1):
    return pd.DataFrame([{"direction": direction, "entry_time": jour(e), "exit_time": jour(s), "entry": entry,
                          "exit": exit, "stop": entry - 5 if direction == "long" else entry + 5, "dist": 5.0,
                          "R": (exit - entry) * (1 if direction == "long" else -1) / 5}])


def cout(direction="long", entry=100.0, exit=110.0, e=0, s=1, h=SANS_COUT, info=INFO, spread=50):
    return appliquer(trade(direction, entry, exit, e, s), bougies(spread), info, h).iloc[0]


# ---------------- prix d'exécution ----------------

def test_prix_execution_toujours_defavorable():
    assert prix_execution(100, 1, "entree", 0.5, 0.1) == pytest.approx(100.6)   # achat au ask + slip
    assert prix_execution(110, 1, "sortie", 0.0, 0.1) == pytest.approx(109.9)   # vente au bid - slip
    assert prix_execution(100, -1, "entree", 0.0, 0.1) == pytest.approx(99.9)   # vente au bid - slip
    assert prix_execution(90, -1, "sortie", 0.5, 0.1) == pytest.approx(90.6)    # rachat au ask + slip


# ---------------- spread ----------------

def test_spread_nul_et_slippage_nul_R_inchange():
    r = cout()
    assert r["R_execution"] == pytest.approx(r["R"]) == pytest.approx(2)
    assert r["entree_exec"] == 100 and r["sortie_exec"] == 110


def test_spread_positif_long_paye_a_l_entree():
    r = cout(h=Hypotheses("fixe", 50, 0, swaps=False))
    assert r["entree_exec"] == pytest.approx(100.5) and r["sortie_exec"] == 110
    assert r["cout_spread_R"] == pytest.approx(0.1)
    assert r["R_execution"] == pytest.approx(1.9)


def test_spread_positif_short_paye_a_la_sortie():
    r = cout("short", 100, 90, h=Hypotheses("fixe", 50, 0, swaps=False))
    assert r["entree_exec"] == 100 and r["sortie_exec"] == pytest.approx(90.5)
    assert r["R_execution"] == pytest.approx(1.9)


def test_spread_historique_avec_plancher():
    r = cout(h=Hypotheses("historique", 10, 0, swaps=False), spread=0)  # bougie à 0 -> plancher 10
    assert r["spread_entree_pts"] == 10 and r["plancher_utilise"]
    r = cout(h=Hypotheses("historique", 10, 0, swaps=False), spread=50)
    assert r["spread_entree_pts"] == 50 and not r["plancher_utilise"]


def test_spread_historique_bougie_absente_refuse():
    t = trade()
    t.loc[0, "entry_time"] = pd.Timestamp("2030-01-01")
    with pytest.raises(CoutInvalide, match="spread absent"):
        appliquer(t, bougies(), INFO, Hypotheses("historique", 10, 0, swaps=False))


@pytest.mark.parametrize("h", [Hypotheses("historique", None), Hypotheses("fixe", -1),
                               Hypotheses("inconnu", 10), Hypotheses("fixe", 10, -1),
                               Hypotheses("fixe", 10, math.nan)])
def test_hypotheses_invalides_refusees(h):
    with pytest.raises(CoutInvalide):
        appliquer(trade(), bougies(), INFO, h)


# ---------------- slippage ----------------

def test_slippage_positif_long_et_short():
    r = cout(h=Hypotheses("fixe", 0, 10, swaps=False))
    assert r["entree_exec"] == pytest.approx(100.1) and r["sortie_exec"] == pytest.approx(109.9)
    assert r["cout_slippage_R"] == pytest.approx(0.04) and r["R_execution"] == pytest.approx(1.96)
    r = cout("short", 100, 90, h=Hypotheses("fixe", 0, 10, swaps=False))
    assert r["entree_exec"] == pytest.approx(99.9) and r["sortie_exec"] == pytest.approx(90.1)
    assert r["R_execution"] == pytest.approx(1.96)


def test_spread_et_slippage_cumules():
    r = cout(h=Hypotheses("fixe", 50, 10, swaps=False))
    assert r["R_execution"] == pytest.approx((109.9 - 100.6) / 5)


@pytest.mark.parametrize("direction", ["long", "short"])
def test_un_cout_ne_devient_jamais_un_gain(direction):
    """Sur des trades gagnants ET perdants, les coûts réduisent toujours le résultat."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        entry, exit = 100.0, float(rng.uniform(80, 120))
        r = cout(direction, entry, exit, e=0, s=int(rng.integers(0, 10)),
                 h=Hypotheses("fixe", float(rng.uniform(0, 100)), float(rng.uniform(0, 50)), swaps=False))
        assert r["R_execution"] <= r["R"] + 1e-12
        assert r["cout_spread_R"] >= 0 and r["cout_slippage_R"] >= 0


# ---------------- swaps : nombre de nuits ----------------

@pytest.mark.parametrize("e,s,attendu", [
    (0, 0, 0),    # intraday : pas de rollover
    (0, 1, 1),    # lundi -> mardi : 1 nuit
    (0, 2, 2),    # lundi -> mercredi
    (0, 3, 5),    # lundi -> jeudi : mercredi compte triple
    (2, 3, 3),    # mercredi -> jeudi : triple seul
    (4, 7, 1),    # vendredi -> lundi : 1 seul swap le vendredi (triple déjà payé mercredi)
    (0, 7, 7),    # lundi -> lundi suivant : 1+1+3+1+1, week-end 0
    (0, 14, 14),  # deux semaines
])
def test_nuits_swap_triple_mercredi(e, s, attendu):
    assert nuits_swap(jour(e), jour(s), "mercredi") == attendu


def test_nuits_swap_triple_vendredi_indices():
    assert nuits_swap(jour(4), jour(7), "vendredi") == 3   # vendredi -> lundi
    assert nuits_swap(jour(2), jour(3), "vendredi") == 1   # mercredi normal


def test_nuits_swap_refuse_jour_inconnu_et_sortie_avant_entree():
    with pytest.raises(CoutInvalide):
        nuits_swap(jour(0), jour(1), "samedi-soir")
    with pytest.raises(CoutInvalide):
        nuits_swap(jour(3), jour(1), "mercredi")


# ---------------- swaps : montants ----------------

def test_swap_negatif_long_plusieurs_nuits():
    r = cout("long", e=0, s=3, h=Hypotheses("fixe", 0, 0))  # 5 nuits x -2 points x 0.01 = -0.10 -> -0.02 R
    assert r["nuits_swap"] == 5 and r["swap_R"] == pytest.approx(-0.02)
    assert r["R_net"] == pytest.approx(r["R_execution"] - 0.02)


def test_swap_positif_short_une_nuit():
    r = cout("short", 100, 90, e=0, s=1, h=Hypotheses("fixe", 0, 0))  # +1 point x 0.01 / 5 = +0.002 R
    assert r["swap_R"] == pytest.approx(0.002) and r["R_net"] == pytest.approx(2.002)


def test_triple_swap_applique():
    r = cout("long", e=2, s=3, h=Hypotheses("fixe", 0, 0))  # mercredi -> jeudi
    assert r["nuits_swap"] == 3 and r["swap_R"] == pytest.approx(3 * -2 * 0.01 / 5)


def test_intraday_aucun_swap_meme_si_swap_non_calculable():
    info = {**INFO, "swap_mode": 3}
    r = cout(e=1, s=1, h=Hypotheses("fixe", 0, 0), info=info)
    assert r["nuits_swap"] == 0 and r["swap_R"] == 0


def test_swaps_desactives_declares():
    r = cout(e=0, s=3, h=Hypotheses("fixe", 0, 0, swaps=False))
    assert r["swap_R"] == 0 and r["R_net"] == r["R_execution"]


def test_swap_manquant_refuse():
    with pytest.raises(CoutInvalide, match="manquant"):
        cout(e=0, s=2, h=Hypotheses("fixe", 0, 0), info={**INFO, "swap_long": math.nan})


@pytest.mark.parametrize("mode", [0, 2, 3, 5, 99])
def test_unite_de_swap_non_convertible_refusee(mode):
    with pytest.raises(CoutInvalide, match="mode"):
        cout(e=0, s=2, h=Hypotheses("fixe", 0, 0), info={**INFO, "swap_mode": mode})


# ---------------- symboles ----------------

def test_symbole_inconnu_refuse(tmp_path):
    f = tmp_path / "swaps.csv"
    pd.DataFrame([{**INFO}]).to_csv(f, sep=";", index=False)
    assert couts.info_symbole("TEST", f)["point"] == 0.01
    with pytest.raises(CoutInvalide, match="inconnu"):
        couts.info_symbole("ABCXYZ", f)


def test_point_invalide_refuse(tmp_path):
    f = tmp_path / "swaps.csv"
    pd.DataFrame([{**INFO, "point": 0}]).to_csv(f, sep=";", index=False)
    with pytest.raises(CoutInvalide, match="point"):
        couts.info_symbole("TEST", f)


reel = pytest.mark.skipif(not couts.SWAPS_CSV.exists(), reason="swaps.csv v0.2 absent")


@reel
def test_swaps_reels_v02_forex_ok_indices_refuses():
    eur = couts.info_symbole("EURUSD")
    assert eur["swap_mode"] == 1 and eur["triple_swap_jour"] == "mercredi"
    with pytest.raises(CoutInvalide, match="mode"):
        cout(e=0, s=2, h=Hypotheses("fixe", 0, 0), info=couts.info_symbole("US500"))


def test_aucun_trade():
    vide = trade().iloc[0:0]
    assert appliquer(vide, bougies(), INFO, SANS_COUT).empty


def test_appliquer_ne_modifie_pas_les_trades_du_moteur():
    t = trade()
    avant = t.copy()
    appliquer(t, bougies(), INFO, Hypotheses("fixe", 50, 10))
    pd.testing.assert_frame_equal(t, avant)


def test_integration_sortie_du_moteur():
    """La table de trades produite par engine.backtest est acceptée telle quelle."""
    from src.engine import Params, backtest
    from tests.test_engine import marche_aleatoire, strategie_honnete
    df = marche_aleatoire()
    df["spread"] = 30
    s = strategie_honnete(df)
    trades, _ = backtest(df, s["signal"], s["stop_dist"], Params(2.0))
    net = appliquer(trades, df, INFO, Hypotheses("historique", 10, 5))
    assert len(net) == len(trades) > 10
    assert (net["R_execution"] < net["R"]).all()
    assert net["R_net"].sum() < net["R"].sum()
